"""共享常量 shim（`horosa-core-js/src/constants/AstroConst.js` / `AstroText.js`）与上游名表的看守（上游 v3.14.0 同步）。

症状（v3.14.0 [盘面细节] 接进来时由上游 jest 样本抓到）：恒星相位行印「月冲轩辕十四」，上游是「月冲狮心轩辕十四」。
根因：上游三张名表（AstroMsg / AstroTxtMsg / AstroMsgCN）以 `AstroConst.X` 为键；共享 AstroConst shim 只有 92 个常量，
缺 49 颗恒星、24 个宫制、月相四象限、八颗汉堡虚星、白羊点 → 这些行全落到 `undefined` 键上，查不到、不报错。
`starNameCn` 查不到 `AstroMsg[星名]` 就回落它自己的次级表（另一套叫法）。AstroText shim 本身还是一份停在 v3.5 的手抄件
（上游 v3.6.0 起的「子女点」名实订正、宿命点、阋神星、希腊化补全六点都没有），不在 vendor 清单里、没有 sha 看守。

既有守卫 `test_shared_astroconst_shim_defines_every_id_its_consumers_reference` 只认 `../constants/AstroConst.js` 这种带
`../` 的引入——AstroText shim 用的是同目录的 `./AstroConst.js`，一直在盲区里。
"""

from __future__ import annotations

from skips import upstream_source  # 上游拆文件后读「门面 + 子模块」全集（v3.15.0）
import json
import re
import shutil
from pathlib import Path

import pytest
from node_esm import run_node_esm
from skips import needs_upstream, upstream_path

CORE_JS = Path(__file__).resolve().parents[1] / "horosa-core-js"
CONST_SHIM = CORE_JS / "src" / "constants" / "AstroConst.js"
TEXT_SHIM = CORE_JS / "src" / "constants" / "AstroText.js"
requires_node = pytest.mark.skipif(shutil.which("node") is None, reason="[host] node not installed")


def missing_astroconst_ids(text_source: str, const_source: str) -> list[str]:
    """AstroText 里当**代码**用到（不算注释）的 `AstroConst.X` 中，AstroConst shim 没有导出的那些。"""
    defined = set(re.findall(r"^export (?:const|function|let) ([A-Za-z_0-9]+)", const_source, flags=re.M))
    code = "\n".join(line.split("//", 1)[0] for line in text_source.split("\n"))
    code = re.sub(r"^import .*$", "", code, flags=re.M)   # `from './AstroConst.js'` 不是引用
    used = dict.fromkeys(re.findall(r"AstroConst\.([A-Za-z_0-9]+)", code))
    return [name for name in used if name not in defined]


def test_astrotext_shim_references_only_ids_the_astroconst_shim_exports() -> None:
    """离线守卫（CI 也跑）：名表的每个键都解析得到。
    负向对照（实跑过）：从 AstroConst shim 删掉 `export const STAR_REGULUS` → 本用例红（['STAR_REGULUS']）。"""
    assert missing_astroconst_ids(TEXT_SHIM.read_text(encoding="utf-8"), CONST_SHIM.read_text(encoding="utf-8")) == []


def test_the_scanner_itself_catches_a_planted_gap() -> None:
    """守卫能抓：内置对照，不依赖有人记得去删常量。"""
    text = "AstroMsg[AstroConst.SUN] = 'A';\nAstroMsg[AstroConst.STAR_PLANTED] = '假星'; // AstroConst.IN_A_COMMENT\n"
    assert missing_astroconst_ids(text, "export const SUN = 'Sun';\n") == ["STAR_PLANTED"]


@requires_node
def test_name_tables_have_no_undefined_key_and_resolve_the_bright_stars() -> None:
    """运行时：三张名表都没有 'undefined' 键；[盘面细节] 恒星相位用到的亮星走上游界面字典的叫法（期望值 = 上游
    constants/AstroText.js:273-322 的字面量；「狮心轩辕十四」另由上游 jest chartDetails.test.js 断言）。"""
    script = (
        "const t = await import(process.argv[1]); const s = await import(process.argv[2]);"
        "const names = JSON.parse(process.argv[3]);"
        "process.stdout.write(JSON.stringify({"
        " undefinedKeys: ['AstroMsg','AstroTxtMsg','AstroMsgCN'].filter((k) => Object.prototype.hasOwnProperty.call(t[k], 'undefined')),"
        " stars: Object.fromEntries(names.map((n) => [n, s.starNameCn(n)])),"
        " sons: t.AstroTxtMsg['Pars Sons'], vertex: t.AstroTxtMsg['Vertex'], whole: t.AstroMsg['Whole Sign'], cupido: t.AstroMsgCN['Cupido'] }));"
    )
    expected = {
        "Regulus": "狮心轩辕十四", "Sirius": "天狼星", "Canopus": "老人星", "Vega": "织女星", "Altair": "牛郎星", "Antares": "蝎心心宿二",
        "Algol": "大陵五", "Spica": "角宿一", "Fomalhaut": "北落师门",
        # 界面字典没有的星 → starNamesCn.js 自己那张表；两张表都没有 → 原名。
        "Mirach": "奎宿九", "NotAStar": "NotAStar",
    }
    out = json.loads(run_node_esm(script, TEXT_SHIM, CORE_JS / "src" / "vendor" / "utils" / "starNamesCn.js", json.dumps(list(expected))))
    assert out["undefinedKeys"] == []
    assert out["stars"] == expected
    assert (out["sons"], out["vertex"], out["whole"], out["cupido"]) == ("子女点", "宿命点", "整宫制", "丘比特")


@needs_upstream("Horosa-Web/astrostudyui/src/constants/AstroText.js", "Horosa-Web/astrostudyui/src/constants/AstroConst.js")
def test_astrotext_shim_is_the_upstream_file_and_new_ids_carry_upstream_values() -> None:
    """AstroText shim = 上游 constants/AstroText.js 全文，唯一改动是 Node ESM 要的 `.js` 后缀（不在 vendor 清单里，这里逐字比）。
    AstroConst shim 里每个字符串常量 == 上游同名常量（既有 test_shared_astroconst_shim_string_ids_equal_upstream_values 同款，
    这里另断言这轮补的那批确实在）。上游 AstroText 一改，本用例红 → 重拷 + 跑 missing_astroconst_ids 补常量。"""
    upstream_text = upstream_source(upstream_path("Horosa-Web/astrostudyui/src/constants/AstroText.js"))
    assert TEXT_SHIM.read_text(encoding="utf-8") == upstream_text.replace(
        "import * as AstroConst from './AstroConst'", "import * as AstroConst from './AstroConst.js'", 1)
    pattern = re.compile(r"^export const ([A-Za-z_0-9]+)\s*=\s*'([^']*)'", re.M)
    upstream_const = dict(pattern.findall(upstream_source(upstream_path("Horosa-Web/astrostudyui/src/constants/AstroConst.js"))))
    mine = dict(pattern.findall(CONST_SHIM.read_text(encoding="utf-8")))
    assert {name: value for name, value in mine.items() if upstream_const.get(name) != value} == {}
    assert {"STAR_REGULUS", "STAR_SIRIUS", "HSYS_Whole_Sign", "HSYS_Fortuna_Whole", "VERTEX", "ERIS", "CUPIDO", "ARIES_POINT",
            "MOON_FIRST_QUARTER", "PARS_BASIS", "PARS_WEDDING_DOROTHEAN"} <= set(mine)
