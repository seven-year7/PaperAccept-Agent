"""
/**
 * @Module: app/agent/paper/nodes/writing_reviewer_node.py
 * @Description: 子图节点 writeAudit（全局 audit）；系统提示词与 OK/REVISE/REPLAN 在 write/agents/global_reviewer_agent.py。
 * @Interface: make_writing_reviewer_node
 */
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from app.agent.paper.state import PaperWorkflowState
from app.agent.paper.write.agents.global_reviewer_agent import run_global_writing_review


def make_writing_reviewer_node(
    event_queue: asyncio.Queue,
    *,
    phase_node: str = "writeAudit",
    route_to_execute: str = "writeExecute",
    route_to_plan: str = "writePlan",
    route_to_done: str = "WRITE_SUBGRAPH_END",
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def writing_reviewer_node(state: PaperWorkflowState) -> Dict[str, Any]:
        return await run_global_writing_review(
            state,
            event_queue,
            phase_node=phase_node,
            route_to_execute=route_to_execute,
            route_to_plan=route_to_plan,
            route_to_done=route_to_done,
        )

    return writing_reviewer_node
