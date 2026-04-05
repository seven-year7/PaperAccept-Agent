"""
/**
 * @Module: app/agent/paper/write/agents/execute_runner.py
 * @Description: 「章节并行写作」独立智能体：每章写；可选知识库检索（PAPER_WRITING_RAG_ENABLED）与章节内审稿（PAPER_SECTION_LOCAL_REVIEW_ENABLED）。
 * @Interface: run_parallel_execute
 *
 * 对应子图节点：writeExecute（入口见 nodes/writing_execute_node.py，仅 SSE）。
 */
"""

from __future__ import annotations

import asyncio
from textwrap import dedent
from typing import Any, Dict, List, Tuple

from langchain_core.prompts import ChatPromptTemplate

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.schemas import ReviewDecision, SectionTask
from app.agent.paper.state import PaperWorkflowState
from app.config import config
from app.tools.knowledge_tool import retrieve_knowledge
from app.utils.paper_workflow_logging import get_paper_logger

# @Agent_Logic: 本节智能体内置「写正文」与「审本节」两套提示词，与 Planner / 全局主编分离。

SECTION_WRITER_SYSTEM_PROMPT = dedent(
    """
    你是学术写作助手。根据章节任务、用户需求、阅读摘要与检索资料撰写本节 Markdown 正文。
    使用三级标题起笔，不要重复输出章节总标题。引用检索内容时概括意涵，勿虚构来源。
    """
).strip()

SECTION_WRITER_HUMAN_PROMPT = (
    "【用户需求】{user_request}\n\n【阅读摘要摘录】\n{reading}\n\n"
    "【全局审稿意见】{global_comment}\n\n"
    "【本节标题】{title}\n【写作目标】{objectives}\n\n"
    "【知识库检索摘录】\n{rag}\n\n【上轮审查意见】{comment}\n\n"
    "请输出修订后的完整本节正文（Markdown）。\n"
)

SECTION_REVIEWER_SYSTEM_PROMPT = dedent(
    """
    你是审稿人。若本节内容已满足 objectives、结构清晰、无明显空洞或与摘要矛盾，输出 APPROVE。
    否则输出 REVISE 并在 comment 给出具体修改建议（中文）。
    """
).strip()

SECTION_REVIEWER_HUMAN_PROMPT = (
    "【本节标题】{title}\n【写作目标】{objectives}\n\n【正文】\n{draft}\n"
)


def _build_section_rag_query(
    task: SectionTask,
    user_request: str,
    writing_comment: str,
    round_idx: int,
    pl,
) -> Tuple[str | None, str]:
    """
    构造本节 retrieve_knowledge 的 query。
    返回 (query 或 None 表示跳过检索用占位正文), 日志用简短原因标签。
    """
    qmax = max(200, int(config.paper_section_rag_query_max_chars))
    base_kw = (task.keywords_for_retrieval or "").strip()
    comment_max = max(0, int(config.paper_section_revise_rag_comment_max_chars))

    revise_tail = ""
    if round_idx > 0 and writing_comment and writing_comment != "（首稿）" and comment_max > 0:
        revise_tail = writing_comment.strip()[:comment_max]

    if base_kw:
        merged = base_kw if not revise_tail else f"{base_kw} {revise_tail}"
        merged = merged.strip()
        if len(merged) > qmax:
            pl.warning(
                f"[PaperWF] section_rag_truncated event=section_query_truncated node=writeExecute "
                f"section_id={task.section_id} len={len(merged)} max={qmax}"
            )
            merged = merged[:qmax]
        pl.info(
            f"[PaperWF] section_rag_query event=section_rag_query_built node=writeExecute "
            f"section_id={task.section_id} round={round_idx} source=keywords preview={merged[:80]!r}..."
        )
        return merged, "keywords"

    if config.paper_section_fallback_rag_from_user_request:
        ur = (user_request or "").strip()[:500] or "学术调研"
        merged = ur if not revise_tail else f"{ur} {revise_tail}"
        merged = merged.strip()
        if len(merged) > qmax:
            pl.warning(
                f"[PaperWF] section_rag_truncated event=section_query_truncated node=writeExecute "
                f"section_id={task.section_id} source=fallback"
            )
            merged = merged[:qmax]
        pl.info(
            f"[PaperWF] section_rag_query event=section_rag_query_built node=writeExecute "
            f"section_id={task.section_id} round={round_idx} source=fallback preview={merged[:80]!r}..."
        )
        return merged, "fallback_user_request"
    if revise_tail:
        merged = revise_tail[:qmax]
        pl.info(
            f"[PaperWF] section_rag_query event=section_rag_query_built node=writeExecute "
            f"section_id={task.section_id} round={round_idx} source=comment_only preview={merged[:80]!r}..."
        )
        return merged, "comment_only"
    return None, "no_keywords"


async def _fetch_rag_for_section(section_id: str, query: str, pl) -> str:
    try:
        content, _docs = await asyncio.to_thread(
            retrieve_knowledge.invoke,
            {"query": query},
        )
        return (content or "")[:8000]
    except Exception as e:
        pl.warning(
            f"[PaperWF] section_rag_fail event=section_retrieve_error node=writeExecute "
            f"section_id={section_id} detail={e!r}"
        )
        return f"（检索失败: {e}）"


async def _run_section_loop(
    task: SectionTask,
    user_request: str,
    reading_excerpt: str,
    global_revision_comment: str,
    pl,
) -> tuple[str, str]:
    section_id = task.section_id
    llm = get_paper_chat_model(temperature=0.4, streaming=False)
    local_review = bool(config.paper_section_local_review_enabled)
    review_llm = None
    if local_review:
        review_llm = get_paper_chat_model(temperature=0.0, streaming=False).with_structured_output(
            ReviewDecision
        )
    max_rounds = (
        max(1, int(config.paper_section_max_revise_rounds)) if local_review else 1
    )

    write_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SECTION_WRITER_SYSTEM_PROMPT),
            ("human", SECTION_WRITER_HUMAN_PROMPT),
        ]
    )
    review_prompt = (
        ChatPromptTemplate.from_messages(
            [
                ("system", SECTION_REVIEWER_SYSTEM_PROMPT),
                ("human", SECTION_REVIEWER_HUMAN_PROMPT),
            ]
        )
        if local_review
        else None
    )

    comment = "（首稿）"
    text = ""
    for round_idx in range(max_rounds):
        # @Step: 1 - 可选 Milvus 检索 → 写；仅在 local_review 时对齐「审」且多轮
        if config.paper_writing_rag_enabled:
            rag_query, _src = _build_section_rag_query(task, user_request, comment, round_idx, pl)
            if rag_query:
                rag_context = await _fetch_rag_for_section(section_id, rag_query, pl)
            else:
                rag_context = "（本节未配置检索关键词）"
        else:
            rag_context = "（未启用写作阶段知识库检索；请仅依据阅读摘要、用户需求与写作目标撰写，勿虚构外部来源。）"

        chain = write_prompt | llm
        draft_msg = await chain.ainvoke(
            {
                "user_request": user_request,
                "reading": reading_excerpt[:6000],
                "global_comment": global_revision_comment or "（无）",
                "title": task.title,
                "objectives": task.objectives,
                "rag": rag_context or "（暂无）",
                "comment": comment,
            }
        )
        text = (
            draft_msg.content
            if hasattr(draft_msg, "content") and draft_msg.content
            else str(draft_msg)
        )

        if not local_review or review_prompt is None or review_llm is None:
            pl.info(
                f"[PaperWF] section_done event=section_write_single node=writeExecute "
                f"section_id={section_id} local_review=false chars={len(text)}"
            )
            return section_id, text

        rev_chain = review_prompt | review_llm
        decision: ReviewDecision = await rev_chain.ainvoke(
            {
                "title": task.title,
                "objectives": task.objectives,
                "draft": text[:12000],
            }
        )
        if decision.decision == "APPROVE":
            pl.info(
                f"[PaperWF] section_review event=section_approved node=writeExecute "
                f"section_id={section_id} round={round_idx}"
            )
            return section_id, text

        comment = decision.comment or "请收紧论述并补充依据。"
        pl.info(
            f"[PaperWF] section_review event=section_revise node=writeExecute "
            f"section_id={section_id} round={round_idx}"
        )

    pl.info(
        f"[PaperWF] section_done event=section_max_rounds node=writeExecute section_id={section_id} "
        f"max_rounds={max_rounds}"
    )
    return section_id, text


async def run_parallel_execute(
    state: PaperWorkflowState,
    *,
    event_queue: asyncio.Queue,
) -> Dict[str, Any]:
    pl = get_paper_logger(state)
    outline: List[Dict[str, Any]] = list(state.get("outline_sections") or [])
    user_request = state.get("user_request") or ""
    reading = state.get("reading_text_for_writing") or ""
    dirty_ids: List[str] = list(state.get("writing_dirty_section_ids") or [])
    global_comment = (state.get("writing_last_review_comment") or "").strip() or "（首稿）"

    if not outline:
        pl.info("[PaperWF] execute_skip event=write_execute_empty node=writeExecute reason=no_outline")
        return {"sections": {}}

    if dirty_ids:
        dset = {str(x).strip() for x in dirty_ids if str(x).strip()}
        to_run = [d for d in outline if str(d.get("section_id") or "") in dset]
    else:
        to_run = list(outline)

    if not to_run:
        pl.info("[PaperWF] execute_skip event=write_execute_empty node=writeExecute reason=no_tasks")
        return {"sections": {}}

    section_ids = [str(d.get("section_id") or "") for d in to_run]
    pl.info(
        f"[PaperWF] execute_start event=write_execute_batch node=writeExecute "
        f"task_count={len(to_run)} dirty_filter={bool(dirty_ids)} "
        f"section_ids={section_ids} rag_enabled={config.paper_writing_rag_enabled}"
    )

    sem = asyncio.Semaphore(max(1, int(config.paper_read_max_concurrent)))

    async def bounded(meta: Dict[str, Any]) -> tuple[str, str]:
        task = SectionTask.model_validate(meta)
        async with sem:
            await event_queue.put(
                {
                    "type": "writing",
                    "data": {"section_id": task.section_id, "status": "start"},
                }
            )
            try:
                sid, body = await _run_section_loop(
                    task,
                    user_request,
                    reading,
                    global_comment,
                    pl,
                )
            finally:
                await event_queue.put(
                    {
                        "type": "writing",
                        "data": {"section_id": task.section_id, "status": "end"},
                    }
                )
            return sid, body

    pairs = await asyncio.gather(*[bounded(d) for d in to_run])
    merged = {sid: body for sid, body in pairs}
    pl.info(
        f"[PaperWF] execute_done event=write_execute_end node=writeExecute "
        f"sections_written={len(merged)} chars_total={sum(len(b or '') for b in merged.values())}"
    )
    return {"sections": merged}
