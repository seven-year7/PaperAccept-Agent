"""
/**
 * @Module: app/utils/rag_request_context.py
 * @Description: RAG 请求级上下文（request_id/session_id/question/user_id/tenant_id）在服务与工具间传递，用于可观测性与租户检索。
 * @Interface: set_rag_request_context / clear_rag_request_context / get_rag_request_context
 */
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional


_rag_request_context_var: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "rag_request_context", default=None
)


def set_rag_request_context(context: Dict[str, Any]) -> None:
    """
    设置当前协程上下文的 RAG 请求信息。

    约束：context 必须是可 JSON 序列化的扁平结构（用于日志输出）。
    """
    _rag_request_context_var.set(context)


def clear_rag_request_context() -> None:
    """清理当前协程上下文的 RAG 请求信息。"""
    _rag_request_context_var.set(None)


def get_rag_request_context() -> Optional[Dict[str, Any]]:
    """获取当前协程上下文的 RAG 请求信息。"""
    return _rag_request_context_var.get()

