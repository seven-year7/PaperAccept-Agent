"""
/**
 * @Module: app/agent/paper/nodes/writing_execute_node.py
 * @Description: 子图节点 writeExecute；章节 Writer/SectionReviewer 提示词与循环在 write/agents/execute_runner.py。
 * @Interface: make_writing_execute_node
 */
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from app.agent.paper.state import PaperWorkflowState
from app.agent.paper.write.agents.execute_runner import run_parallel_execute


def make_writing_execute_node(
    event_queue: asyncio.Queue,
    *,
    phase_node: str = "writeExecute",
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def writing_execute_node(state: PaperWorkflowState) -> Dict[str, Any]:
        await event_queue.put(
            {"type": "phase", "data": {"node": phase_node, "status": "start", "detail": {}}}
        )
        out = await run_parallel_execute(state, event_queue=event_queue)
        sections = dict(out.get("sections") or {})
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": phase_node,
                    "status": "end",
                    "detail": {"sections_written": len(sections)},
                },
            }
        )
        return out

    return writing_execute_node
