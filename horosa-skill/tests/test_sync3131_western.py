"""星阙 v3.13.1（Horosa-Public 965af0f4..06f25f21）西占本命 / 龙盘的两个新设置 + 口径自陈行手抄表看守。

上游来源：
- `utils/classicalParamSpec.js:104-112` 新增古典全局键 `sunriseMode`（center 缺省 / apparent，send:'nonDefault'）；
  `utils/astroAiSnapshot.js:331/374-377` CLS_CALIBRE_LABELS + CLS_CALIBRE_HEAD_DEFAULTS 插入 sunriseMode；
  后端 `perchart_parts/timing.py:36-111`（日出 / 日没视口径）+ helper.py:245 / webchartsrv.py:116 / webmodernsrv.py:58 白名单。
- `components/auxchart/AstroDraconicLab.js:19-25/69/80` 龙盘「宫位口径」（请求键 draconicHouses：whole 缺省 / shift），
  快照 [龙盘] 恒多一行「宫位口径：…」；后端 `astroextra_parts/progressions.py:441` + `thirteenthchart.py:167-205`。

旧代码为什么会红：skill 不认这两个键 —— sunriseMode 不进 [起盘信息] 古典口径行（CLASSICAL_PARAM_SPEC 镜像缺项，
vendored classicalParamSpec.js 一换就让 test_sync311_chartexport 的镜像测试红），draconicHouses 既不校验也不出宫位口径行；
显式传缺省值会原样下发（上游「缺省不发 = 零回归」）。
负向对照（逐项实跑过）：① 删 _CLS_CALIBRE_HEAD_DEFAULTS 的 sunriseMode → test_calibre_head_defaults_match_upstream 红（口径行
本身仍对：overrides 尾段按 spec 补出，序恰同 —— 所以要逐键对上游的看守）；② 删 CLASSICAL_PARAM_SPEC_NON_DEFAULT 的 sunriseMode →
test_sync311_chartexport::test_classical_param_spec_mirror_matches_vendored_js 红；③ 删 _CLS_CALIBRE_LABELS 的 sunriseMode →
口径行测试 + 上游看守红；④ runner 改成恒下发 draconicHouses → test_draconic_default_does_not_send_house_mode 红；⑤ 删 runner 宫位
口径行 → 两条龙盘段测试红；⑥ 校验器不再把 center 归一成 None → schema / 下发两条 sunriseMode 测试红。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fakes import CaptureClient, FakeJsClient
from pydantic import ValidationError

from horosa_skill.astro_rulers import (
    DRACONIC_HOUSE_LABELS,
    DRACONIC_HOUSE_MODE_DEFAULT,
    DRACONIC_HOUSE_MODES,
    SUNRISE_MODE_DEFAULT,
    SUNRISE_MODES,
)
from horosa_skill.config import Settings
from horosa_skill.engine import astro_snapshot as snap
from horosa_skill.memory.store import MemoryStore
from horosa_skill.schemas.tools import BirthInput
from horosa_skill.schemas.tools.astro import DraconicInput
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_schema import advertise_hidden_fields

_ROOT = os.environ.get("HOROSA_SOURCE_ROOT")
_UI = Path(_ROOT) / "Horosa-Web" / "astrostudyui" / "src" if _ROOT else None
requires_upstream = pytest.mark.skipif(
    _UI is None or not (_UI / "utils" / "astroAiSnapshot.js").is_file(), reason="HOROSA_SOURCE_ROOT (Horosa-Public checkout) not set"
)

_BIRTH = {"date": "1990-05-04", "time": "12:30:00", "zone": "+08:00", "lat": "31n14", "lon": "121e30", "agent_confirmed_settings": True}


def _service(tmp_path, client) -> HorosaSkillService:
    settings = Settings(
        server_root="http://127.0.0.1:9", runtime_root=tmp_path / "runtime", db_path=tmp_path / "memory.db", output_dir=tmp_path / "runs",
    )
    return HorosaSkillService(settings, client=client, store=MemoryStore(settings), js_client=FakeJsClient())


def _sent(client: CaptureClient, endpoint: str) -> list[dict]:
    return [payload for ep, payload in client.calls if ep == endpoint]


# ─────────────────────────── sunriseMode ───────────────────────────
def test_sunrise_mode_schema_drops_default_and_rejects_unknown() -> None:
    assert BirthInput.model_validate({**_BIRTH, "sunriseMode": "apparent"}).sunriseMode == "apparent"
    # 缺省档不下发（上游 send:'nonDefault'）：显式 center 归一成 None → model_dump(exclude_none) 不带此键。
    assert "sunriseMode" not in BirthInput.model_validate({**_BIRTH, "sunriseMode": "center"}).model_dump(exclude_none=True)
    with pytest.raises(ValidationError):
        BirthInput.model_validate({**_BIRTH, "sunriseMode": "upper_limb"})
    assert (SUNRISE_MODE_DEFAULT, SUNRISE_MODES) == ("center", ("center", "apparent"))


def test_sunrise_mode_forwarded_to_chart_only_when_non_default(tmp_path) -> None:
    """本命盘主请求（每次 run 的第一个远程调用）：apparent 下发、显式 center 不下发（缺省请求体零变）。"""
    client = CaptureClient()
    service = _service(tmp_path, client)
    service.run_tool("chart", {**_BIRTH, "sunriseMode": "apparent"}, save_result=False)
    first_apparent = client.calls[0][1]
    client.calls.clear()
    service.run_tool("chart", {**_BIRTH, "sunriseMode": "center"}, save_result=False)
    first_center = client.calls[0][1]
    assert first_apparent.get("sunriseMode") == "apparent"
    assert first_center.get("date") == first_apparent.get("date") and "sunriseMode" not in first_center


def test_sunrise_mode_apparent_lands_in_calibre_line() -> None:
    """astroAiSnapshot.js:391-419 buildClassicalCalibreLine：头键 sunriseMode 非缺省才列（标签 :331）。"""
    assert snap.build_classical_calibre_line({"sunriseMode": "apparent"}) == "古典口径（非默认项）：日出 / 日没口径=日面上缘·含大气折射。"
    assert snap.build_classical_calibre_line({"sunriseMode": "center"}) == ""
    # 头键先于 overrides 尾键：与 sectBuffer 同列时按 CLS_CALIBRE_HEAD_DEFAULTS 序（sectBuffer → sunriseMode）。
    assert snap.build_classical_calibre_line({"sectBuffer": "apparent", "sunriseMode": "apparent"}) == (
        "古典口径（非默认项）：区分判定=视地平(含折射)；日出 / 日没口径=日面上缘·含大气折射。"
    )


def test_sunrise_mode_is_hidden_from_tools_list_but_documented() -> None:
    from horosa_skill.western_options_doc import western_options_doc

    assert BirthInput.model_fields["sunriseMode"].description
    assert "sunriseMode" in western_options_doc("chart")
    assert "sunriseMode" in western_options_doc("horary")
    assert "sunriseMode" not in western_options_doc("india_chart")   # 印占不随此项（IndiaChartKernel 恒视日出）


@requires_upstream
def test_calibre_head_defaults_match_upstream() -> None:
    """astroAiSnapshot.js CLS_CALIBRE_HEAD_DEFAULTS 逐键逐值（含键序）+ 新增 sunriseMode 标签。"""
    text = (_UI / "utils" / "astroAiSnapshot.js").read_text(encoding="utf-8")
    block = text[text.index("const CLS_CALIBRE_HEAD_DEFAULTS = {"):]
    block = block[block.index("{") + 1: block.index("};")]
    upstream = []
    for key, raw in re.findall(r"(\w+):\s*('[^']*'|-?\d+)", block):
        upstream.append((key, raw.strip("'") if raw.startswith("'") else int(raw)))
    assert list(snap._CLS_CALIBRE_HEAD_DEFAULTS.items()) == upstream
    m = re.search(r"sunriseMode: \{ label: '([^']*)', map: \{ apparent: '([^']*)' \} \}", text)
    assert m is not None
    label, mapping, _fmt = snap._CLS_CALIBRE_LABELS["sunriseMode"]
    assert (label, mapping) == (m.group(1), {"apparent": m.group(2)})
    spec = (_UI / "utils" / "classicalParamSpec.js").read_text(encoding="utf-8")
    entry = spec[spec.index("{ key: 'sunriseMode'"):]
    entry = entry[: entry.index("] },")]
    assert re.search(r"default: '([^']*)'", entry).group(1) == SUNRISE_MODE_DEFAULT
    assert tuple(re.findall(r"value: '([^']*)'", entry)) == SUNRISE_MODES


# ─────────────────────────── draconicHouses ───────────────────────────
def test_draconic_house_mode_schema() -> None:
    assert "draconicHouses" in advertise_hidden_fields(DraconicInput)
    assert DraconicInput.model_validate({**_BIRTH, "draconicHouses": "shift"}).draconicHouses == "shift"
    with pytest.raises(ValidationError):
        DraconicInput.model_validate({**_BIRTH, "draconicHouses": "equal"})


def _draconic_section(result: dict) -> list[str]:
    text = result["data"]["export_snapshot"]["export_text"]
    body = text[text.index("[龙盘]\n") + len("[龙盘]\n"):]
    return body.split("\n\n")[0].split("\n")


def test_draconic_default_does_not_send_house_mode(tmp_path) -> None:
    client = CaptureClient()
    result = _service(tmp_path, client).run_tool("draconic", {**_BIRTH}, save_result=False).model_dump(mode="json")
    assert "draconicHouses" not in _sent(client, "/astroextra/draconic")[0]   # 缺键 = 整宫 = v3.13.0 请求体
    lines = _draconic_section(result)
    assert lines[0].startswith("北交点 123.45°（平交点）")
    assert lines[1] == "宫位口径：整宫(随龙盘上升)"   # AstroDraconicLab.js:80 无条件 push


def test_draconic_shift_sends_house_mode_and_states_it(tmp_path) -> None:
    client = CaptureClient()
    result = _service(tmp_path, client).run_tool(
        "draconic", {**_BIRTH, "draconicHouses": "shift"}, save_result=False
    ).model_dump(mode="json")
    assert _sent(client, "/astroextra/draconic")[0]["draconicHouses"] == "shift"
    assert _draconic_section(result)[1] == "宫位口径：本命宫头平移(保留分宫制)，各星落宫与本命一致"
    settings = result["data"]["technique_card"]["settings"]
    assert settings["draconicHouses"]["value"] == "shift"


@requires_upstream
def test_draconic_house_vocab_matches_upstream() -> None:
    text = (_UI / "components" / "auxchart" / "AstroDraconicLab.js").read_text(encoding="utf-8")
    modes = re.search(r"export const DRACONIC_HOUSE_MODES = \[([^\]]*)\]", text).group(1)
    assert tuple(re.findall(r"'([^']*)'", modes)) == DRACONIC_HOUSE_MODES
    labels = re.search(r"const DRACONIC_HOUSE_LABELS = \{([^}]*)\}", text).group(1)
    assert dict(re.findall(r"(\w+): '([^']*)'", labels)) == DRACONIC_HOUSE_LABELS
    assert re.search(r"houseMode: \{ label: '宫位口径', def: '(\w+)'", text).group(1) == DRACONIC_HOUSE_MODE_DEFAULT
    assert "out.push(`宫位口径：${DRACONIC_HOUSE_LABELS[houseMode] || DRACONIC_HOUSE_LABELS.whole}${houseMode === 'shift' ? '，各星落宫与本命一致' : ''}`);" in text
