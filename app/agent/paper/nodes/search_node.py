"""
/**
 * @Module: app/agent/paper/nodes/search_node.py
 * @Description: 将用户需求转为结构化 arXiv 查询；可选人工确认后再检索论文列表。
 * @Interface: make_search_agent_node
 */
"""

from __future__ import annotations

import asyncio
from textwrap import dedent
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from langchain_core.prompts import ChatPromptTemplate

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.schemas import (
    PaperMeta,
    StructuredArxivQuery,
    normalize_structured_arxiv_query,
)
from app.agent.paper.state import PaperWorkflowState
from app.config import config
from app.services.paper_search_confirm_gate import (
    apply_confirmation_to_structured,
    build_post_search_confirm_boundary_event,
    build_search_confirm_event,
    format_search_confirm_assistant_markdown,
    wait_for_search_confirmation,
)
from app.services.paper_search_query_refiner import refine_structured_with_adjustment_text
from app.tools.paper_arxiv_tool import PaperSearcher, preview_arxiv_search_query
from app.utils.paper_workflow_logging import get_paper_logger

# LLM 结构化失败时的英文兜底（避免全中文 user_request 直接进 all: 导致召回差）
_FALLBACK_ENGLISH_QUERYS = ("machine learning", "deep learning", "neural network")


def make_search_agent_node(
    event_queue: asyncio.Queue,
    *,
    confirm_queue: Optional[asyncio.Queue] = None,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def search_agent_node(state: PaperWorkflowState) -> Dict[str, Any]:
        pl = get_paper_logger(state)
        run_id = str(state.get("run_id") or "")
        user_request = state.get("user_request") or ""
        human_confirm_enabled = bool(
            confirm_queue is not None and config.paper_search_human_confirm_enabled
        )

        await event_queue.put(
            {"type": "phase", "data": {"node": "search", "status": "start", "detail": {}}}
        )

        try:
            llm = get_paper_chat_model(temperature=0.1, streaming=False)
            structured_llm = llm.with_structured_output(StructuredArxivQuery)
            prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        dedent(
                            """
                            你是学术文献检索助手。将用户的自然语言需求转为 arXiv 检索参数。
                            - querys：2～5 条关键词短语，**优先使用英文**（arXiv 以英文为主）；若用户仅写中文，请给出对应英译或通用英文学术检索词。
                            - 用户明确「按论文标题找」时填写 title_phrase（优先英文短语）；明确「某作者」时填写 author（姓名，可含空格）。
                            - start_date / end_date：若用户明确时间范围则填 YYYY-MM-DD，否则留空字符串。
                            - sort_mode：用户强调「最新」「最近发表」「按时间」等填 submitted_date；否则填 relevance。
                            - categories：仅当用户明确学科/arxiv 分区时填写，如机器学习 cs.LG、人工智能 cs.AI；不确定则空列表。
                            仅输出结构化字段，不要解释。
                            """
                        ).strip(),
                    ),
                    ("human", "{user_request}"),
                ]
            )
            chain = prompt | structured_llm
            structured = cast(
                StructuredArxivQuery,
                await chain.ainvoke({"user_request": user_request}),
            )
        except Exception as e:
            pl.warning(
                f"[PaperWF] search_structured_fallback event=llm_struct_fail node=search detail={e!r}"
            )
            structured = StructuredArxivQuery(querys=list(_FALLBACK_ENGLISH_QUERYS))

        structured = normalize_structured_arxiv_query(structured)

        if human_confirm_enabled and confirm_queue is not None:
            assistant_md = format_search_confirm_assistant_markdown(
                run_id=run_id,
                structured=structured,
                user_request_preview=user_request,
            )
            await event_queue.put({"type": "content", "data": assistant_md})
            await event_queue.put(
                build_search_confirm_event(run_id, structured, user_request)
            )
            timeout_sec = float(config.paper_search_confirm_timeout_sec or 0)
            msg = await wait_for_search_confirmation(
                run_id=run_id,
                confirm_queue=confirm_queue,
                timeout_sec=timeout_sec,
                paper_log=pl,
            )
            adj = str(msg.get("adjustment_text") or "").strip()
            if adj and config.paper_search_confirm_refiner_enabled:
                structured = await refine_structured_with_adjustment_text(
                    structured, adj, paper_log=pl
                )
            structured = apply_confirmation_to_structured(structured, msg)
            await event_queue.put(build_post_search_confirm_boundary_event(run_id))

        preview_q = preview_arxiv_search_query(structured)
        pl.info(
            f"[PaperWF] search_arxiv_query_ready event=query_built node=search "
            f"query_terms_count={len(structured.querys)} "
            f"used_title_phrase={bool(structured.title_phrase)} used_author={bool(structured.author)} "
            f"sort_mode={structured.sort_mode} categories_count={len(structured.categories)} "
            f"human_confirm={human_confirm_enabled} final_arxiv_query_preview={preview_q[:240]!r}"
        )

        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": "search",
                    "status": "progress",
                    "detail": {"structured_query": structured.model_dump()},
                },
            }
        )

        searcher = PaperSearcher()
        try:
            papers: list[PaperMeta] = await searcher.search(structured)
        except Exception as e:
            pl.error(f"[PaperWF] search_arxiv_failed event=arxiv_invoke_error node=search detail={e!r}")
            raise RuntimeError(f"arxiv_search: {e}") from e

        paper_dicts = [p.model_dump() for p in papers]
        pl.info(
            f"[PaperWF] search_complete event=search_end node=search "
            f"paper_count={len(paper_dicts)} human_confirm={human_confirm_enabled}"
        )
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": "search",
                    "status": "end",
                    "detail": {"paper_count": len(paper_dicts)},
                },
            }
        )
        return {
            "structured_query": structured.model_dump(),
            "papers": paper_dicts,
        }

    return search_agent_node
