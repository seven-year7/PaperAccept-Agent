"""
/**
 * @Module: app/utils/paper_workflow_logging.py
 * @Description: 论文工作流日志 trace：统一 run_id/session_id/tenant_id，与 rag_request_context.request_id 对齐，便于按单次 run grep 全链路。
 * @Interface: paper_trace_extra / get_paper_logger / get_paper_logger_from_context / log_paper_event
 */
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from loguru import logger

from app.utils.rag_request_context import get_rag_request_context


def paper_trace_extra(state: Mapping[str, Any]) -> dict[str, str]:
    """从 PaperWorkflowState 或任意 dict 提取可追溯字段。"""
    return {
        "paper_run_id": str(state.get("run_id") or ""),
        "paper_session_id": str(state.get("session_id") or ""),
        "paper_tenant_id": str(state.get("tenant_id") or ""),
    }


def get_paper_logger(state: Mapping[str, Any]):
    """绑定论文链路 trace 的 logger；与全局 format 中 extra 字段配合。"""
    extra = paper_trace_extra(state)
    return logger.bind(
        paper_run_id=extra["paper_run_id"],
        paper_session_id=extra["paper_session_id"],
        paper_tenant_id=extra["paper_tenant_id"],
        paper_component="PaperWF",
    )


def get_paper_logger_from_context():
    """
    在无 state 的场景（如 to_thread 内工具）使用：依赖 rag_request_context。
    request_id 与论文 run_id 一致（见 paper_workflow_service）。
    """
    ctx = get_rag_request_context() or {}
    return logger.bind(
        paper_run_id=str(ctx.get("request_id") or ""),
        paper_session_id=str(ctx.get("session_id") or ""),
        paper_tenant_id=str(ctx.get("tenant_id") or ""),
        paper_component="PaperWF",
    )


def log_paper_event(
    level: str,
    state: Optional[Mapping[str, Any]],
    message: str,
    *,
    event: str = "",
    node: str = "",
    **fields: Any,
) -> None:
    """
    单行结构化论文事件日志（message 内带 [PaperWF] 与 k=v 片段，便于无 bind 环境或双重保险）。
    """
    log = get_paper_logger(state) if state is not None else get_paper_logger_from_context()
    fragments: list[str] = []
    if event:
        fragments.append(f"event={event}")
    if node:
        fragments.append(f"node={node}")
    for k, v in fields.items():
        if v is not None and v != "":
            fragments.append(f"{k}={v}")
    tail = " ".join(fragments)
    line = f"[PaperWF] {message}" + (f" {tail}" if tail else "")
    log_method = getattr(log, level.lower(), None)
    if log_method is None:
        log_method = log.info
    log_method(line)
