from __future__ import annotations

import pytest

from horosa_skill.schemas.tools import DispatchInput, KnowledgeReadInput, KnowledgeRegistryInput
from horosa_skill.surfaces.mcp_server import _normalize_mcp_request


def test_normalize_mcp_request_accepts_json_string_for_empty_request() -> None:
    payload = _normalize_mcp_request("{}", KnowledgeRegistryInput)
    assert payload == {}


def test_normalize_mcp_request_accepts_json_string_for_structured_request() -> None:
    payload = _normalize_mcp_request(
        '{"domain":"qimen","category":"door","key":"休门"}',
        KnowledgeReadInput,
    )
    assert payload == {"domain": "qimen", "category": "door", "key": "休门"}


def test_normalize_mcp_request_accepts_plain_dict() -> None:
    payload = _normalize_mcp_request({"query": "起一张当前星盘"}, DispatchInput)
    assert payload["query"] == "起一张当前星盘"
    assert payload["save_result"] is True


def test_normalize_mcp_request_rejects_non_object_payload() -> None:
    with pytest.raises(ValueError, match="request must be an object"):
        _normalize_mcp_request('["not","an","object"]', KnowledgeRegistryInput)
