"""
/**
 * @Module: app/agent/paper/node_guard.py
 * @Description: 论文工作流节点异常：硬失败 wrap_paper_node（抛 PaperNodeError）；软失败 wrap_paper_node_soft（写 *_node_error，图经 condition_handler 收尾）。
 * @Interface: wrap_paper_node / wrap_paper_node_soft / PaperNodeError
 */
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from app.agent.paper.state import PaperWorkflowState
from app.utils.paper_workflow_logging import get_paper_logger


class PaperNodeError(Exception):
    """节点已推送 SSE error 后的包装异常，服务层勿重复推送。"""

    def __init__(self, node_id: str, message: str) -> None:
        super().__init__(message)
        self.node_id = node_id


def wrap_paper_node(
    node_id: str,
    inner: Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]],
    event_queue: asyncio.Queue,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    """
    包装 LangGraph 节点：异常时 logger.exception、队列 error、再 raise PaperNodeError。
    """

    async def guarded(state: PaperWorkflowState) -> Dict[str, Any]:
        run_id = str(state.get("run_id") or "")
        try:
            return await inner(state)
        except PaperNodeError:
            raise
        except Exception as e:
            pl = get_paper_logger(state)
            pl.exception(
                f"[PaperWF] paper_node_error event=node_exception node={node_id} "
                f"error_type={type(e).__name__}"
            )
            await event_queue.put(
                {
                    "type": "error",
                    "data": {
                        "node": node_id,
                        "message": str(e),
                        "run_id": run_id,
                    },
                }
            )
            raise PaperNodeError(node_id, str(e)) from e

    return guarded


def wrap_paper_node_soft(
    node_id: str,
    error_state_key: str,
    inner: Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]],
    event_queue: asyncio.Queue,
    *,
    phase_sse_node: str | None = None,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    """
    软失败包装：异常时推送 SSE error、可选 phase end，并返回 {error_state_key: message}，不抛错，供 condition_handler 转 error_finalize。
    """

    async def soft_guarded(state: PaperWorkflowState) -> Dict[str, Any]:
        run_id = str(state.get("run_id") or "")
        try:
            return await inner(state)
        except PaperNodeError:
            raise
        except Exception as e:
            pl = get_paper_logger(state)
            pl.exception(
                f"[PaperWF] paper_node_soft_fail event=node_soft_fail node={node_id} "
                f"error_state_key={error_state_key} error_type={type(e).__name__}"
            )
            await event_queue.put(
                {
                    "type": "error",
                    "data": {
                        "node": node_id,
                        "message": str(e),
                        "run_id": run_id,
                    },
                }
            )
            if phase_sse_node:
                await event_queue.put(
                    {
                        "type": "phase",
                        "data": {
                            "node": phase_sse_node,
                            "status": "end",
                            "detail": {"error": True, "message": (str(e))[:500]},
                        },
                    }
                )
            return {error_state_key: str(e)}

    return soft_guarded
