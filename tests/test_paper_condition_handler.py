"""
/**
 * @Module: tests/test_paper_condition_handler.py
 * @Description: 论文五车间 condition_handler 与写作子图后主图路由的单元测试。
 */
"""

from __future__ import annotations

from langgraph.graph import END

from app.agent.paper.condition_handler import (
    collect_registered_errors,
    is_paper_workflow_failed_state,
    route_after_stage,
    route_after_write_node,
)


def test_route_after_search_ok_goes_reading():
    s: dict = {}
    assert route_after_stage(s, "search") == "reading"


def test_route_after_search_error_goes_finalize():
    s = {"search_node_error": "arxiv down"}
    assert route_after_stage(s, "search") == "error_finalize"


def test_route_after_report_ok_goes_end():
    s: dict = {}
    assert route_after_stage(s, "report") == END


def test_route_after_write_replan_goes_analysis():
    s = {"writing_route_next": "writePlan"}
    assert route_after_write_node(s) == "analysis"


def test_route_after_write_ok_goes_report():
    s = {"writing_route_next": "WRITE_SUBGRAPH_END"}
    assert route_after_write_node(s) == "report"


def test_route_after_write_error_goes_finalize():
    s = {"writing_node_error": "boom"}
    assert route_after_write_node(s) == "error_finalize"


def test_collect_registered_errors():
    s = {"search_node_error": "a", "reading_node_error": "b"}
    out = collect_registered_errors(s)
    assert "search:" in out and "reading:" in out


def test_is_paper_workflow_failed_state():
    assert is_paper_workflow_failed_state({}) is False
    assert is_paper_workflow_failed_state({"workflow_failed": True}) is True
    assert is_paper_workflow_failed_state({"report_node_error": "x"}) is True
