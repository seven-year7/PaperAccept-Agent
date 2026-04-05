"""
/**
 * @Module: app/agent/paper/nodes/error_finalize_node.py
 * @Description: 流水线失败收尾：标记 workflow_failed、汇总 errors、LLM 生成兜底说明并通过 SSE content 推送。
 * @Interface: make_error_finalize_node
 */
"""

from __future__ import annotations

import asyncio
from textwrap import dedent
from typing import Any, Awaitable, Callable, Dict

from langchain_core.messages import HumanMessage

from app.agent.paper.condition_handler import collect_registered_errors
from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.state import PaperWorkflowState
from app.utils.paper_workflow_logging import get_paper_logger


def make_error_finalize_node(
    event_queue: asyncio.Queue,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def error_finalize_node(state: PaperWorkflowState) -> Dict[str, Any]:
        pl = get_paper_logger(state)
        await event_queue.put(
            {
                "type": "phase",
                "data": {"node": "error_finalize", "status": "start", "detail": {}},
            }
        )
        summary = collect_registered_errors(state)
        if not summary.strip():
            summary = "未登记具体车间错误（可能为路由异常）。"
        user_request = (state.get("user_request") or "").strip()[:2000]
        err_block = summary[:6000]

        prompt = dedent(
            f"""
            你是助手。论文调研流水线已在某一车间失败，无法生成完整报告。
            请根据下列「错误登记表」与用户需求，用中文写一段简短说明（200～500 字）：
            - 说明未能完成的原因（不编造细节）；
            - 建议用户可采取的下一步（如修改需求、检查网络、关闭人工确认超时等）。

            【用户需求】
            {user_request}

            【错误登记表】
            {err_block}
            """
        ).strip()

        llm = get_paper_chat_model(temperature=0.2, streaming=False)
        fallback = ""
        try:
            resp = await llm.ainvoke([HumanMessage(content=prompt)])
            fallback = (
                (resp.content or "").strip()
                if hasattr(resp, "content")
                else str(resp).strip()
            )
        except Exception as e:
            pl.warning(f"[PaperWF] error_finalize_llm_fail event=fallback_llm_error detail={e!r}")
            fallback = f"论文工作流已中断。\n\n{summary}\n\n请根据上述信息排查后重试。"

        if not fallback:
            fallback = f"论文工作流已中断。\n\n{summary}"

        await event_queue.put({"type": "content", "data": fallback})
        summary_line = f"[workflow_failed] {summary[:800]}"
        pl.info(f"[PaperWF] error_finalize_end event=error_finalize_end node=error_finalize chars={len(fallback)}")
        await event_queue.put(
            {
                "type": "phase",
                "data": {"node": "error_finalize", "status": "end", "detail": {"chars": len(fallback)}},
            }
        )
        return {
            "workflow_failed": True,
            "fallback_answer": fallback,
            "errors": [summary_line],
        }

    return error_finalize_node
