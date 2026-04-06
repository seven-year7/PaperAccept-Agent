"""
/**
 * @Module: app/agent/paper/graph.py
 * @Description: 论文主图：search → reading → write（子图：writePlan→execute→audit）→ report；每车间结束经 condition_handler；失败转 error_finalize → END。
 * @Interface: build_paper_graph
 */
"""

from __future__ import annotations

import asyncio

from langgraph.graph import END, START, StateGraph

from app.agent.paper.condition_handler import route_after_stage, route_after_write_node
from app.agent.paper.node_guard import wrap_paper_node_soft
from app.agent.paper.nodes.error_finalize_node import make_error_finalize_node
from app.agent.paper.nodes.reading_node import make_reading_agent_node
from app.agent.paper.nodes.report_node import make_report_agent_node
from app.agent.paper.nodes.search_node import make_search_agent_node
from app.agent.paper.state import PaperWorkflowState
from app.agent.paper.write_subgraph import build_paper_write_subgraph


def build_paper_graph(
    event_queue: asyncio.Queue,
    confirm_queue: asyncio.Queue | None = None,
):
    """编译论文工作流主图；大纲规划在写作子图首节点 writePlan。"""
    write_subgraph = build_paper_write_subgraph(event_queue)

    builder = StateGraph(PaperWorkflowState)
    builder.add_node(
        "search",
        wrap_paper_node_soft(
            "search",
            "search_node_error",
            make_search_agent_node(event_queue, confirm_queue=confirm_queue),
            event_queue,
            phase_sse_node="search",
        ),
    )
    builder.add_node(
        "reading",
        wrap_paper_node_soft(
            "reading",
            "reading_node_error",
            make_reading_agent_node(event_queue),
            event_queue,
            phase_sse_node="reading",
        ),
    )
    builder.add_node("write", write_subgraph)
    builder.add_node(
        "report",
        wrap_paper_node_soft(
            "report",
            "report_node_error",
            make_report_agent_node(event_queue),
            event_queue,
            phase_sse_node="report",
        ),
    )
    builder.add_node("error_finalize", make_error_finalize_node(event_queue))

    builder.add_edge(START, "search")
    builder.add_conditional_edges(
        "search",
        lambda s: route_after_stage(s, "search"),
        {
            "reading": "reading",
            "error_finalize": "error_finalize",
        },
    )
    builder.add_conditional_edges(
        "reading",
        lambda s: route_after_stage(s, "reading"),
        {
            "write": "write",
            "error_finalize": "error_finalize",
        },
    )
    builder.add_conditional_edges(
        "write",
        route_after_write_node,
        {
            "report": "report",
            "error_finalize": "error_finalize",
        },
    )
    builder.add_conditional_edges(
        "report",
        lambda s: route_after_stage(s, "report"),
        {
            END: END,
            "error_finalize": "error_finalize",
        },
    )
    builder.add_edge("error_finalize", END)

    return builder.compile()
