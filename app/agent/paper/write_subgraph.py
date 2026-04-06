"""
/**
 * @Module: app/agent/paper/write_subgraph.py
 * @Description: 写作子图（车间「写作」）：writePlan → writeExecute → writeAudit → 条件回路；REPLAN 时回到子图内 writePlan。
 * @Interface: build_paper_write_subgraph / WRITE_SUBGRAPH_ROUTE_END
 */
"""

from __future__ import annotations

import asyncio

from langgraph.graph import END, START, StateGraph

from app.agent.paper.node_guard import wrap_paper_node_soft
from app.agent.paper.nodes.writing_execute_node import make_writing_execute_node
from app.agent.paper.nodes.writing_plan_node import make_writing_plan_node
from app.agent.paper.nodes.writing_reviewer_node import make_writing_reviewer_node
from app.agent.paper.state import PaperWorkflowState

WRITE_SUBGRAPH_ROUTE_END = "WRITE_SUBGRAPH_END"


def route_after_write_plan(state: PaperWorkflowState) -> str:
    """writePlan 之后：若已登记写作错误则结束子图，否则进入章节写作。"""
    if (state.get("writing_node_error") or "").strip():
        return WRITE_SUBGRAPH_ROUTE_END
    return "writeExecute"


def route_after_write_execute(state: PaperWorkflowState) -> str:
    """writeExecute 之后：若已登记写作错误则直接结束子图，否则进入全局审稿。"""
    if (state.get("writing_node_error") or "").strip():
        return WRITE_SUBGRAPH_ROUTE_END
    return "writeAudit"


def route_after_write_audit(state: PaperWorkflowState) -> str:
    """writeAudit 之后：若写作失败则结束子图；REPLAN 回到子图内 writePlan；否则 REVISE/OK 按原语义。"""
    if (state.get("writing_node_error") or "").strip():
        return WRITE_SUBGRAPH_ROUTE_END
    nxt = (state.get("writing_route_next") or WRITE_SUBGRAPH_ROUTE_END).strip()
    if nxt in ("writePlan", "writing_plan"):
        return "writePlan"
    if nxt in (WRITE_SUBGRAPH_ROUTE_END, "report", "END", "__end__"):
        return WRITE_SUBGRAPH_ROUTE_END
    if nxt == "writeExecute":
        return "writeExecute"
    if nxt == "writing_execute":
        return "writeExecute"
    return WRITE_SUBGRAPH_ROUTE_END


def build_paper_write_subgraph(event_queue: asyncio.Queue):
    """编译写作子图；入口为 writePlan（大纲规划），其后 execute/audit 与 REPLAN 回路。"""
    builder = StateGraph(PaperWorkflowState)
    builder.add_node(
        "writePlan",
        wrap_paper_node_soft(
            "writePlan",
            "writing_node_error",
            make_writing_plan_node(event_queue, phase_node="writePlan"),
            event_queue,
            phase_sse_node="writePlan",
        ),
    )
    builder.add_node(
        "writeExecute",
        wrap_paper_node_soft(
            "writeExecute",
            "writing_node_error",
            make_writing_execute_node(event_queue, phase_node="writeExecute"),
            event_queue,
            phase_sse_node="writeExecute",
        ),
    )
    builder.add_node(
        "writeAudit",
        wrap_paper_node_soft(
            "writeAudit",
            "writing_node_error",
            make_writing_reviewer_node(
                event_queue,
                phase_node="writeAudit",
                route_to_execute="writeExecute",
                route_to_plan="writePlan",
                route_to_done=WRITE_SUBGRAPH_ROUTE_END,
            ),
            event_queue,
            phase_sse_node="writeAudit",
        ),
    )

    builder.add_edge(START, "writePlan")
    builder.add_conditional_edges(
        "writePlan",
        route_after_write_plan,
        {
            "writeExecute": "writeExecute",
            WRITE_SUBGRAPH_ROUTE_END: END,
        },
    )
    builder.add_conditional_edges(
        "writeExecute",
        route_after_write_execute,
        {
            "writeAudit": "writeAudit",
            WRITE_SUBGRAPH_ROUTE_END: END,
        },
    )
    builder.add_conditional_edges(
        "writeAudit",
        route_after_write_audit,
        {
            "writePlan": "writePlan",
            "writeExecute": "writeExecute",
            WRITE_SUBGRAPH_ROUTE_END: END,
        },
    )

    return builder.compile()
