"""
/**
 * @Module: app/agent/paper/condition_handler.py
 * @Description: 论文五车间流水线「下一步去哪」：检查对应车间错误登记表，失败则转 error_finalize，否则进下一车间或 END。
 * @Interface: route_after_stage
 */
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END

from app.agent.paper.state import PaperWorkflowState

CompletedStage = Literal["search", "reading", "analysis", "report"]

_STAGE_ERROR_KEY: dict[CompletedStage, str] = {
    "search": "search_node_error",
    "reading": "reading_node_error",
    "analysis": "analysis_node_error",
    "writing": "writing_node_error",
    "report": "report_node_error",
}


def _stage_failed(state: PaperWorkflowState, completed: CompletedStage) -> bool:
    key = _STAGE_ERROR_KEY[completed]
    return bool((state.get(key) or "").strip())


def route_after_stage(state: PaperWorkflowState, completed: CompletedStage) -> str:
    """
    刚完成 completed 车间后的路由：
    - 该车间的 *_node_error 非空 → error_finalize
    - 否则 → 下一车间；report 成功后 → END（LangGraph 常量）
    """
    # @Step: 1 - 与需求一致：有登记错误则不进下一车间
    if _stage_failed(state, completed):
        return "error_finalize"
    if completed == "search":
        return "reading"
    if completed == "reading":
        return "analysis"
    if completed == "analysis":
        return "write"
    if completed == "report":
        return END
    return "error_finalize"


def route_after_write_node(state: PaperWorkflowState) -> str:
    """
    主图在「写作」子图整段执行结束后的路由：
    - 写作登记错误 → error_finalize
    - 子图因 REPLAN 退出且 writing_route_next 指向 writePlan → 回到 analysis
    - 否则 → report
    """
    if (state.get("writing_node_error") or "").strip():
        return "error_finalize"
    nxt = (state.get("writing_route_next") or "").strip()
    if nxt in ("writePlan", "writing_plan"):
        return "analysis"
    return "report"


def is_paper_workflow_failed_state(state: PaperWorkflowState) -> bool:
    """成功跑完全图且无车间登记错误、且未走 error_finalize 时为 False。"""
    if state.get("workflow_failed"):
        return True
    for key in _STAGE_ERROR_KEY.values():
        if (state.get(key) or "").strip():
            return True
    return False


def collect_registered_errors(state: PaperWorkflowState) -> str:
    """拼成一段供 error_finalize / LLM 使用的摘要（截断由各调用方控制）。"""
    lines: list[str] = []
    for stage, key in _STAGE_ERROR_KEY.items():
        msg = (state.get(key) or "").strip()
        if msg:
            lines.append(f"{stage}: {msg}")
    return "\n".join(lines)
