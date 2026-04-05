"""paper_search_query_refiner 单元测试（不调用真实 LLM）。"""

from __future__ import annotations

import pytest

from app.agent.paper.schemas import StructuredArxivQuery
from app.config import config
from app.services.paper_search_query_refiner import refine_structured_with_adjustment_text


class _MemLog:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)


@pytest.mark.asyncio
async def test_refiner_empty_adjustment_noop():
    base = StructuredArxivQuery(querys=["a"])
    log = _MemLog()
    out = await refine_structured_with_adjustment_text(base, "  \n  ", paper_log=log)
    assert out.querys == base.querys
    assert not log.warnings


@pytest.mark.asyncio
async def test_refiner_skips_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "openrouter_api_key", "")
    base = StructuredArxivQuery(querys=["a"])
    log = _MemLog()
    out = await refine_structured_with_adjustment_text(
        base, "only 2024 papers", paper_log=log
    )
    assert out.model_dump() == base.model_dump()
    assert any("no_openrouter" in w for w in log.warnings)
