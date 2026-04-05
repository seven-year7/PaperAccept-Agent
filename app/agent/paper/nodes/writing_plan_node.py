"""
/**
 * @Module: app/agent/paper/nodes/writing_plan_node.py
 * @Description: 大纲规划节点；主图节点 id 为 `analysis`，SSE phase.node 默认仍为 writePlan。逻辑在 write/agents/plan_agent.py。
 * @Interface: make_writing_plan_node
 */
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict

from app.agent.paper.state import PaperWorkflowState
from app.agent.paper.write.agents.plan_agent import run_writing_plan


def make_writing_plan_node(
    event_queue: asyncio.Queue,
    *,
    phase_node: str = "writePlan",
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def writing_plan_node(state: PaperWorkflowState) -> Dict[str, Any]:
        await event_queue.put(
            {"type": "phase", "data": {"node": phase_node, "status": "start", "detail": {}}}
        )
        patch = await run_writing_plan(state)
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": phase_node,
                    "status": "end",
                    "detail": {"section_count": len(patch.get("outline_sections") or [])},
                },
            }
        )
        return patch

    return writing_plan_node
