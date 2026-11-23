"""上游 v3.15.0 同步 · 六壬 / 金口诀「问测人出生」（挂载设置 querentBirth / querentGender）。

上游 regenCase.querentRunYearOf：没有存档行年时，行年按年差法（resolveDisplayRunYear）、本命支按出生公历年、出生年柱按本地
八字（正午）；交给起课法本命 / 行年各档、[行年] 段与金口诀属相 / 虚岁。skill 在 tools/liureng.js 逐行移植（上游文件拖着整个
无头重算树，不 vendor），这里用上游自己的用例（utils/__tests__/regenMundane.test.js「问测人出生 → 行年 / 本命」）当金标。
负向对照：runLiureng 不用 querentRunYearOf（runyear 仍取 payload.runyear）→ 六壬两条红；jinkou 不接 → 金口诀那条红。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from node_esm import run_node_esm
from test_sync311_sanshi import _lr, _replay_service, _run, _section

from horosa_skill.schemas.tools.cn_divination import JinKouInput, LiuRengGodsInput

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"


def _querent(*cases: dict) -> list:
    script = ("const m = await import(process.argv[1]); const cases = JSON.parse(process.argv[2]);"
              "process.stdout.write(JSON.stringify(cases.map((c) => m.querentRunYearOf(c.gua, c.zone, c.p))));")
    return json.loads(run_node_esm(script, CORE_JS / "src" / "tools" / "liureng.js", json.dumps(list(cases))))


def test_upstream_cases() -> None:
    gua = "2026-11-13 10:24:00"
    male, female, none, kept = _querent(
        {"gua": gua, "zone": "+08:00", "p": {"querentBirth": "1990-05-06"}},
        {"gua": gua, "zone": "+08:00", "p": {"querentBirth": "1990-05-06", "querentGender": "female"}},
        {"gua": gua, "zone": "+08:00", "p": {}},
        {"gua": gua, "zone": "+08:00", "p": {"querentBirth": "1990-05-06", "runyear": {"year": "甲子"}}},
    )
    assert male["runyear"]["age"] == 36 and isinstance(male["runyear"]["year"], str) and male["runyear"]["year"]
    assert male["runyear"]["birthGanZi"] == "庚午" and male["benmingZhi"] == "午"
    assert male["xingnianZhi"] == male["runyear"]["year"][1]
    assert female["runyear"]["year"] != male["runyear"]["year"], "男顺女逆"
    assert none is None and kept is None


def test_liureng_querent_feeds_the_benming_cast_and_the_runyear_section(tmp_path) -> None:
    plain = _lr(tmp_path, options={"castMethod": "bmjs"})
    with_q = _lr(tmp_path, options={"castMethod": "bmjs"}, querentBirth="1991-05-06", querentGender="male")
    # 本命加时：本命支取问测人出生年（1991 辛未 → 未），不是起课年（2026 丙午 → 午）→ 四课跟着变
    # （别用 1990：庚午与起课年同为午支，四课恰好不变，测不出东西）
    assert _section(with_q["snapshot_text"], "四课") != _section(plain["snapshot_text"], "四课")
    assert _section(plain["snapshot_text"], "行年") == "无"
    # 1991 → 2026 年差 35，男顺行
    assert _section(with_q["snapshot_text"], "行年").splitlines()[1] == "年龄：35岁"


def test_jinkou_querent_reaches_the_runyear_section(tmp_path) -> None:
    service, _client = _replay_service(tmp_path)
    plain = _run(service, "jinkou_default")
    with_q = _run(service, "jinkou_default", querentBirth="1990-05-06")
    assert plain.ok and with_q.ok, (plain.error, with_q.error)
    assert _section(plain.data["snapshot_text"], "行年") == "无"
    assert _section(with_q.data["snapshot_text"], "行年").splitlines()[:2] == ["行年干支：壬寅", "年龄：36岁"]


@pytest.mark.parametrize(("field", "bad"), [("querentBirth", "1990/5/6"), ("querentBirth", "五月"), ("querentGender", "x")])
def test_bad_querent_values_are_refused(field, bad) -> None:
    base = {"date": "2026-04-04", "time": "21:18:00", "zone": "+08:00", "lat": "31n13", "lon": "121e28"}
    for model in (LiuRengGodsInput, JinKouInput):
        with pytest.raises(Exception) as err:
            model(**base, **{field: bad})
        assert field in str(err.value)
    ok = LiuRengGodsInput(**base, querentBirth="1990-05-06", querentGender="女")
    assert ok.querentGender == "female"
