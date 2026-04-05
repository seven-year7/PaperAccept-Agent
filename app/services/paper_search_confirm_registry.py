"""
/**
 * @Module: app/services/paper_search_confirm_registry.py
 * @Description: 论文工作流「检索前人工确认」：按 run_id 挂接 asyncio.Queue，供 SSE 与 confirm API 共享。
 * @Interface: register_run / unregister_run / submit_search_confirmation
 */
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Dict, Optional

_lock = threading.Lock()
_run_queues: Dict[str, asyncio.Queue] = {}


def register_run(run_id: str) -> asyncio.Queue:
    """为本次论文运行注册单槽确认队列（仅接受一条确认消息）。"""
    q: asyncio.Queue = asyncio.Queue(maxsize=1)
    with _lock:
        _run_queues[run_id] = q
    return q


def unregister_run(run_id: str) -> None:
    with _lock:
        _run_queues.pop(run_id, None)


def submit_search_confirmation(run_id: str, payload: Dict[str, Any]) -> bool:
    """
    投递人工确认。成功表示已入队；run_id 未知或已确认过则返回 False。
    """
    with _lock:
        q: Optional[asyncio.Queue] = _run_queues.get(run_id)
    if q is None:
        return False
    try:
        q.put_nowait(payload)
    except asyncio.QueueFull:
        return False
    return True
