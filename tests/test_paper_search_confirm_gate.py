"""paper_search_confirm_gate 单元测试（不跑论文整图）。"""

from __future__ import annotations

import asyncio
from typing import Any, List

import pytest

from app.agent.paper.schemas import StructuredArxivQuery
from app.services.paper_search_confirm_gate import (
    CONFIRM_RUN_ID_MISMATCH_MAX,
    POST_SEARCH_CONFIRM_BOUNDARY_REASON,
    apply_confirmation_to_structured,
    build_post_search_confirm_boundary_event,
    build_search_confirm_event,
    format_search_confirm_assistant_markdown,
    wait_for_search_confirmation,
)


class _MemLog:
    def __init__(self) -> None:
        self.warnings: List[str] = []
        self.errors: List[str] = []
        self.infos: List[str] = []

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def info(self, msg: str) -> None:
        self.infos.append(msg)


def test_format_search_confirm_assistant_markdown_contains_run_id_and_fields():
    sq = StructuredArxivQuery(
        querys=["openclaw", "agent"],
        start_date="2024-01-01",
        end_date="",
        title_phrase="",
        author="",
        sort_mode="relevance",
        categories=["cs.AI"],
    )
    text = format_search_confirm_assistant_markdown(
        run_id="run-abc",
        structured=sq,
        user_request_preview="帮我查 openclaw 论文",
    )
    assert "run-abc" in text
    assert "openclaw" in text
    assert "querys" in text
    assert "cs.AI" in text
    assert "结构化条件" in text


def test_build_search_confirm_event_shape():
    sq = StructuredArxivQuery(querys=["q1", "q2"])
    ev = build_search_confirm_event("run-1", sq, "user text " * 200)
    assert ev["type"] == "search_confirm"
    d = ev["data"]
    assert d["run_id"] == "run-1"
    assert d["structured_query"]["querys"] == ["q1", "q2"]
    assert len(d["user_request_preview"]) <= 800
    assert "confirm_search" in d["message"]
    assert "TitlePhrase" in d["message"]


def test_build_post_search_confirm_boundary_event_shape():
    ev = build_post_search_confirm_boundary_event("run-boundary-1")
    assert ev["type"] == "assistant_message_boundary"
    d = ev["data"]
    assert d["run_id"] == "run-boundary-1"
    assert d["reason"] == POST_SEARCH_CONFIRM_BOUNDARY_REASON
    assert d["reason"] == "post_search_confirm"
    assert isinstance(d.get("label"), str) and d["label"]


def test_apply_confirmation_title_author_categories_sort():
    base = StructuredArxivQuery(
        querys=["old"],
        title_phrase="",
        author="",
        categories=[],
        sort_mode="relevance",
    )
    msg: dict[str, Any] = {
        "approved": True,
        "title_phrase": "  neural network  ",
        "author": " Hinton ",
        "categories": [" cs.AI ", "cs.LG"],
        "sort_mode": "submitted_date",
    }
    out = apply_confirmation_to_structured(base, msg)
    assert out.title_phrase == "neural network"
    assert out.author == "Hinton"
    assert "cs.AI" in out.categories and "cs.LG" in out.categories
    assert out.sort_mode == "submitted_date"
    assert out.querys


def test_apply_confirmation_querys_and_dates():
    base = StructuredArxivQuery(
        querys=["a"],
        start_date="",
        end_date="",
        title_phrase="t",
        author="",
        sort_mode="relevance",
        categories=["cs.LG"],
    )
    msg: dict[str, Any] = {
        "run_id": "x",
        "approved": True,
        "querys": ["  new1 ", "", "new2"],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }
    out = apply_confirmation_to_structured(base, msg)
    assert "new1" in out.querys and "new2" in out.querys
    assert out.start_date == "2024-01-01"
    assert out.end_date == "2024-12-31"
    assert out.title_phrase == "t"
    assert out.categories == ["cs.LG"]


def test_apply_confirmation_empty_override_keeps_querys():
    base = StructuredArxivQuery(querys=["keep"])
    msg = {"approved": True, "querys": []}
    out = apply_confirmation_to_structured(base, msg)
    assert out.querys


@pytest.mark.asyncio
async def test_wait_for_search_confirmation_success():
    q: asyncio.Queue = asyncio.Queue()
    log = _MemLog()

    async def _sender() -> None:
        await asyncio.sleep(0.05)
        await q.put(
            {
                "run_id": "rid",
                "approved": True,
                "querys": ["x"],
            }
        )

    asyncio.create_task(_sender())
    msg = await wait_for_search_confirmation(
        run_id="rid",
        confirm_queue=q,
        timeout_sec=5.0,
        paper_log=log,
    )
    assert msg["approved"] is True


@pytest.mark.asyncio
async def test_wait_for_search_confirmation_timeout():
    q: asyncio.Queue = asyncio.Queue()
    log = _MemLog()
    with pytest.raises(RuntimeError, match="search_confirm_timeout"):
        await wait_for_search_confirmation(
            run_id="rid",
            confirm_queue=q,
            timeout_sec=0.05,
            paper_log=log,
        )
    assert log.errors


@pytest.mark.asyncio
async def test_wait_for_search_confirmation_rejected():
    q: asyncio.Queue = asyncio.Queue()
    log = _MemLog()
    await q.put({"run_id": "rid", "approved": False, "reason": "no thanks"})
    with pytest.raises(RuntimeError, match="search_rejected"):
        await wait_for_search_confirmation(
            run_id="rid",
            confirm_queue=q,
            timeout_sec=5.0,
            paper_log=log,
        )
    assert log.infos


@pytest.mark.asyncio
async def test_wait_for_run_id_mismatch_then_success():
    q: asyncio.Queue = asyncio.Queue()
    log = _MemLog()
    await q.put({"run_id": "wrong", "approved": True})
    await q.put({"run_id": "good", "approved": True})
    msg = await wait_for_search_confirmation(
        run_id="good",
        confirm_queue=q,
        timeout_sec=5.0,
        paper_log=log,
    )
    assert msg["run_id"] == "good"
    assert len(log.warnings) == 1


@pytest.mark.asyncio
async def test_wait_for_too_many_mismatches():
    q: asyncio.Queue = asyncio.Queue()
    log = _MemLog()
    for i in range(CONFIRM_RUN_ID_MISMATCH_MAX):
        await q.put({"run_id": f"bad{i}", "approved": True})
    with pytest.raises(RuntimeError, match="search_confirm_mismatch"):
        await wait_for_search_confirmation(
            run_id="target",
            confirm_queue=q,
            timeout_sec=5.0,
            paper_log=log,
        )
    assert len(log.warnings) == CONFIRM_RUN_ID_MISMATCH_MAX
