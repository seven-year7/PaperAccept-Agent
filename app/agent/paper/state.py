"""
/**
 * @Module: app/agent/paper/state.py
 * @Description: LangGraph 论文工作流共享状态与 reducer。
 * @Interface: PaperWorkflowState
 */
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, Optional

from typing_extensions import TypedDict


def merge_sections(left: Optional[Dict[str, str]], right: Optional[Dict[str, str]]) -> Dict[str, str]:
    """合并各章节正文。"""
    a = dict(left or {})
    a.update(dict(right or {}))
    return a


class PaperWorkflowState(TypedDict, total=False):
    run_id: str
    user_request: str
    session_id: str
    tenant_id: str
    workspace_dir: str
    structured_query: Dict[str, Any]
    papers: List[Dict[str, Any]]
    readings_md_path: str
    reading_text_for_writing: str
    outline_sections: List[Dict[str, Any]]
    sections: Annotated[Dict[str, str], merge_sections]
    # 写作子图 writePlan / writeExecute / writeAudit；已进入全局 audit 并成功调用评审 LLM 的次数（上限见 PAPER_WRITING_MAX_REVIEWER_INVOCATIONS）
    writing_reviewer_invocations: int
    writing_route_next: str
    writing_replan_hint: str
    writing_replan_affected_ids: List[str]
    writing_last_review_comment: str
    writing_dirty_section_ids: List[str]
    planning_knowledge_excerpt: str
    errors: Annotated[List[str], operator.add]
    assembled_report: str
    final_report_path: str
    # 五车间错误登记表：非空表示该车间的失败原因（软失败，图经 condition_handler 转 error_finalize）
    search_node_error: str
    reading_node_error: str
    analysis_node_error: str
    writing_node_error: str
    report_node_error: str
    workflow_failed: bool
    fallback_answer: str
