"""
/**
 * @Module: app/agent/paper/llm_utils.py
 * @Description: 论文工作流共用 ChatOpenAI（OpenRouter 兼容）。
 * @Interface: get_paper_chat_model
 */
"""

from __future__ import annotations

from typing import Any, cast

from langchain_openai import ChatOpenAI

from app.config import config


def paper_model_name() -> str:
    m = (config.paper_model or "").strip()
    return m if m else config.rag_model


def get_paper_chat_model(*, temperature: float = 0.2, streaming: bool = False) -> ChatOpenAI:
    return ChatOpenAI(
        model=paper_model_name(),
        api_key=cast(Any, config.openrouter_api_key),
        base_url=config.openrouter_api_base,
        temperature=temperature,
        streaming=streaming,
    )
