"""v0.48.0 tools/list 瘦身的结构性守卫（全量面 −10.4 KB / 精简面 −0.45 KB，零参数增删、零改名改型）。

总量棘轮（`scripts/verify_mcp_list_budget.py`）有 2% 容差 ≈ 5 KB：一句共享描述每份涨 20 B、乘上 100 个工具也能悄悄溜过去。
这里按「每一份」锁三件事：
① 技法描述尾行不再带 `(tool_name="…")`——模型手里就是本工具名，guidance 两种写法都收；
② `aka:` 不重复描述首段里已作为整词出现的词，且原来 aka 行给的每个词仍作为整词留在描述里（信息不丢）；
③ 每个技法都广告的共享字段（域核心 + 闸门三键 + `request`）单份字节有上限：这里 +1 B = 全量面 +N B。
"""
from __future__ import annotations

import asyncio
import json
import re

import pytest
from fakes import FakeClient, FakeJsClient

from horosa_skill.config import Settings
from horosa_skill.engine.registry import TOOL_DEFINITIONS
from horosa_skill.engine.synonyms import aka_line
from horosa_skill.memory.store import MemoryStore
from horosa_skill.service import HorosaSkillService
from horosa_skill.surfaces.mcp_schema import AKA_LIMIT, GUIDANCE_TAIL
from horosa_skill.surfaces.mcp_server import create_mcp_server

# 单份上限（字节，按 verify_mcp_list_budget 同一量法：json.dumps(ensure_ascii=False)）= v0.48.0 瘦身后的实测值。
# 要加字就先在别处省出 N 倍；宫制 hsys 不在表里：它的图例由宫制表派生，由 test_house_system_docs / test_enums_are_locked_to_their_tables 锁。
SHARED_FIELD_CAP_BYTES: dict[str, int] = {
    "date": 65,
    "time": 56,
    "zone": 67,
    "lat": 61,
    "lon": 63,
    "ad": 67,
    "zodiacal": 83,
    "siderealAyanamsa": 93,
    "response_view": 104,
    "gender": 48,
    "timeAlg": 64,
    "agent_confirmed_settings": 66,
    "defaults_accepted": 63,
    "clarification_notes": 49,
    "request": 100,
}


def _bytes(obj: object) -> int:
    return len(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


@pytest.fixture(scope="module")
def full_tools(tmp_path_factory) -> dict[str, dict]:
    tmp = tmp_path_factory.mktemp("slim")
    settings = Settings(db_path=tmp / "memory.db", output_dir=tmp / "runs", mcp_compact=False)
    service = HorosaSkillService(settings, client=FakeClient(), store=MemoryStore(settings), js_client=FakeJsClient())
    mcp = create_mcp_server(service, settings)
    return {tool.name: tool.model_dump(mode="json", by_alias=True) for tool in asyncio.run(mcp.list_tools())}


def _technique_tools(full_tools: dict[str, dict]) -> dict[str, dict]:
    by_mcp = {definition.mcp_name: name for name, definition in TOOL_DEFINITIONS.items()}
    out = {by_mcp[name]: tool for name, tool in full_tools.items() if name in by_mcp}
    assert len(out) == len(TOOL_DEFINITIONS)
    return out


def _split(description: str) -> tuple[str, list[str]]:
    head, _, tail = description.partition("\n")
    match = re.match(r"aka: (.*?)；", tail)
    return head, (match.group(1).split(", ") if match else [])


def _is_word_char(ch: str) -> bool:
    return (ch.isascii() and ch.isalnum()) or "\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff"


def _has_term(text: str, word: str) -> bool:
    """`word` 逐字出现、且两侧不是字母数字 / 汉字（整词）。用 str.find 自己扫，不借实现里的正则，免得拿实现验实现。"""
    hay, needle = text.lower(), word.lower()
    start = 0
    while (i := hay.find(needle, start)) != -1:
        before = hay[i - 1] if i > 0 else " "
        end = i + len(needle)
        after = hay[end] if end < len(hay) else " "
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        start = i + 1
    return False


def test_guidance_tail_does_not_repeat_the_tool_name(full_tools) -> None:
    techniques = _technique_tools(full_tools)
    wrong = [tool["name"] for tool in techniques.values() if not tool["description"].endswith(GUIDANCE_TAIL)]
    assert not wrong, f"技法描述必须以共享尾行结尾：{wrong[:5]}"
    named = [tool["name"] for tool in techniques.values() if "tool_name=" in tool["description"]]
    assert not named, f"尾行又带上了本工具名（114 份 × ~25 B）：{named[:5]}"


def test_aka_skips_words_already_in_the_description_without_losing_any(full_tools) -> None:
    techniques = _technique_tools(full_tools)
    repeated: list[tuple[str, str]] = []
    lost: list[tuple[str, str]] = []
    for tool_name, tool in techniques.items():
        description = tool["description"]
        head, aka = _split(description)
        repeated.extend((tool_name, word) for word in aka if _has_term(head, word))
        # 去重前的 aka 行（同一个 AKA_LIMIT）给模型 / 工具搜索看的每个词，去重后仍要在这条描述里**作为整词**出现：
        # 「星盘」嵌在「西洋星盘」里不算，按词切的搜索索引里它会消失。
        legacy = aka_line(tool_name, limit=AKA_LIMIT).removeprefix("aka: ")
        lost.extend((tool_name, word) for word in (legacy.split(", ") if legacy else []) if not _has_term(description, word))
    assert not repeated, f"aka 重复了描述首段里已有的词：{repeated[:5]}"
    assert not lost, f"aka 去重丢了词（描述里已不是整词）：{lost[:5]}"


def test_shared_fields_cost_at_most_their_cap_per_copy(full_tools) -> None:
    widest: dict[str, int] = {}
    copies: dict[str, int] = {}
    for tool in full_tools.values():
        for name, prop in (tool["inputSchema"].get("properties") or {}).items():
            if name in SHARED_FIELD_CAP_BYTES:
                widest[name] = max(widest.get(name, 0), _bytes(prop))
                copies[name] = copies.get(name, 0) + 1
    assert set(widest) == set(SHARED_FIELD_CAP_BYTES), set(SHARED_FIELD_CAP_BYTES) ^ set(widest)
    over = {
        name: f"{widest[name]} B > {cap} B（× {copies[name]} 个工具）"
        for name, cap in SHARED_FIELD_CAP_BYTES.items()
        if widest[name] > cap
    }
    assert not over, f"共享字段单份变胖，全量面按份数放大：{over}"
