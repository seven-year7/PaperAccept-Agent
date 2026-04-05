"""chat_intent_router 单元测试与 chat_stream 首包 route 烟测（无真实 LLM / 无 Milvus）。"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.config import config
from app.services import chat_intent_router as cir
from app.services.chat_intent_router import ChatIntentResult, resolve_chat_intent


@pytest.fixture
def chat_only_app():
    app = FastAPI()
    app.include_router(chat_api.router, prefix="/api")
    return app


@pytest.mark.asyncio
async def test_force_route_rag(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", True)
    r = await resolve_chat_intent("文献综述", force_route="rag")
    assert r.branch == "rag_chat"
    assert r.source == "forced_rag"


@pytest.mark.asyncio
async def test_force_route_paper(monkeypatch):
    r = await resolve_chat_intent("hi", force_route="paper")
    assert r.branch == "paper_workflow"
    assert r.source == "forced_paper"
    assert "hi" in r.effective_user_request("hi")


@pytest.mark.asyncio
async def test_rule_greeting_general_rag(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", False)
    r = await resolve_chat_intent("你好")
    assert r.branch == "rag_chat"
    assert r.source == "rule"


@pytest.mark.asyncio
async def test_rule_keyword_paper_workflow(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", False)
    r = await resolve_chat_intent("请帮我做一份关于 RAG 的文献综述大纲")
    assert r.branch == "paper_workflow"
    assert r.source == "rule"
    assert r.confidence == 1.0


@pytest.mark.asyncio
async def test_llm_disabled_fallback_rag(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", False)
    r = await resolve_chat_intent("totally_unique_query_xyz_no_keyword_match_12345")
    assert r.branch == "rag_chat"
    assert r.source == "rule"


@pytest.mark.asyncio
async def test_llm_classify_paper(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", True)

    async def fake_llm(_q: str) -> cir._LLMIntentSchema:
        return cir._LLMIntentSchema(
            intent="paper_workflow",
            confidence=0.95,
            normalized_user_request="norm topic",
        )

    monkeypatch.setattr(cir, "_classify_with_llm", fake_llm)
    r = await resolve_chat_intent("totally_unique_query_xyz_no_keyword_match_12345")
    assert r.branch == "paper_workflow"
    assert r.source == "llm"
    assert r.effective_user_request("totally_unique_query_xyz_no_keyword_match_12345") == "norm topic"


@pytest.mark.asyncio
async def test_llm_low_confidence_downgrades(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", True)
    monkeypatch.setattr(config, "chat_paper_route_confidence_threshold", 0.9)

    async def fake_llm(_q: str) -> cir._LLMIntentSchema:
        return cir._LLMIntentSchema(
            intent="paper_workflow",
            confidence=0.5,
            normalized_user_request="x",
        )

    monkeypatch.setattr(cir, "_classify_with_llm", fake_llm)
    r = await resolve_chat_intent("unique_low_conf_abc")
    assert r.branch == "rag_chat"


@pytest.mark.asyncio
async def test_llm_failure_downgrades(monkeypatch):
    monkeypatch.setattr(config, "chat_paper_route_llm_enabled", True)

    async def fake_llm(_q: str) -> None:
        return None

    monkeypatch.setattr(cir, "_classify_with_llm", fake_llm)
    r = await resolve_chat_intent("unique_fail_abc")
    assert r.branch == "rag_chat"


def test_chat_stream_first_event_is_route_when_paper(monkeypatch, chat_only_app):
    monkeypatch.setattr(config, "chat_paper_route_enabled", True)

    async def fixed_resolve(*_a, **_k):
        return ChatIntentResult(
            intent="paper_workflow",
            branch="paper_workflow",
            confidence=1.0,
            source="forced_paper",
            normalized_user_request="demo topic",
        )

    async def fake_paper_stream(*, user_request, session_id, tenant_id):
        yield {"type": "done", "data": {"ok": True, "run_id": "fake-run"}}

    monkeypatch.setattr(chat_api, "resolve_chat_intent", fixed_resolve)
    monkeypatch.setattr(chat_api, "run_paper_research_stream", fake_paper_stream)

    with TestClient(chat_only_app) as client:
        with client.stream(
            "POST",
            "/api/chat_stream",
            json={
                "Id": "pytest-chat-stream",
                "Question": "anything",
                "UserId": "u",
                "TenantId": "t",
                "ForceRoute": "paper",
            },
        ) as resp:
            assert resp.status_code == 200
            buf = b""
            for chunk in resp.iter_bytes(chunk_size=8192):
                buf += chunk
                if b"\n\n" in buf:
                    break
    text = buf.decode("utf-8", errors="replace")
    assert "event: message" in text
    first_data = None
    for line in text.splitlines():
        if line.startswith("data: "):
            first_data = json.loads(line[6:])
            break
    assert first_data is not None
    assert first_data.get("type") == "route"
    assert first_data.get("data", {}).get("branch") == "paper_workflow"
