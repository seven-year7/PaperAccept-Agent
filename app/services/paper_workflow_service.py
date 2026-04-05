"""
/**
 * @Module: app/services/paper_workflow_service.py
 * @Description: 论文工作流编排：LangGraph + asyncio.Queue 桥接 SSE。
 * @Interface: run_paper_research_stream
 */
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict

from loguru import logger

from app.agent.paper.condition_handler import is_paper_workflow_failed_state
from app.agent.paper.graph import build_paper_graph
from app.agent.paper.node_guard import PaperNodeError
from app.config import config
from app.services.paper_search_confirm_registry import register_run, unregister_run
from app.utils.paper_workflow_logging import get_paper_logger
from app.utils.rag_request_context import clear_rag_request_context, set_rag_request_context


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _paper_run_timestamp_str() -> str:
    """工作区目录名用时间前缀，精确到分，不含非法路径字符。"""
    if config.paper_workspace_timestamp_utc:
        dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d_%H%M")


def _allocate_workspace_dir(root: Path, rel: Path) -> tuple[str, Path]:
    """
    分配工作区目录名（与 run_id 一致）。同分钟冲突时追加 _2、_3…

    Returns:
        (run_id, 已 mkdir 的绝对路径)
    """
    base_ts = _paper_run_timestamp_str()
    parent = (root / rel).resolve()
    parent.mkdir(parents=True, exist_ok=True)

    run_id = base_ts
    ws = (parent / run_id).resolve()
    counter = 2
    while counter <= 10_000:
        try:
            ws.mkdir(exist_ok=False)
            logger.info(f"[PaperWF] workspace_allocated run_id={run_id} path={ws}")
            return run_id, ws
        except FileExistsError:
            run_id = f"{base_ts}_{counter}"
            ws = (parent / run_id).resolve()
            counter += 1
    raise RuntimeError(
        f"无法分配论文工作区目录（同分钟内重试过多）: base={base_ts!r}"
    )


async def run_paper_research_stream(
    *,
    user_request: str,
    session_id: str,
    tenant_id: str,
) -> AsyncIterator[Dict[str, Any]]:
    """
    执行论文工作流，异步产出 SSE 负载字典（由路由层 JSON 序列化）。

    Yields:
        阶段/内容/完成/错误事件，直至 type == done。
    """
    root = _project_root()
    rel = Path(config.paper_workspace_root)
    run_id, ws = _allocate_workspace_dir(root, rel)

    event_queue: asyncio.Queue = asyncio.Queue()
    confirm_queue: asyncio.Queue | None = None
    if config.paper_search_human_confirm_enabled:
        confirm_queue = register_run(run_id)
    graph = build_paper_graph(event_queue, confirm_queue=confirm_queue)

    init_state: Dict[str, Any] = {
        "run_id": run_id,
        "user_request": user_request.strip(),
        "session_id": session_id,
        "tenant_id": tenant_id,
        "workspace_dir": str(ws),
        "papers": [],
        "sections": {},
        "errors": [],
    }

    ctx = {
        "request_id": run_id,
        "session_id": session_id,
        "tenant_id": tenant_id,
        "question": user_request[:500],
    }
    set_rag_request_context(ctx)

    final_out: Dict[str, Any] = {}
    timeout_ms = config.paper_workflow_timeout_ms or 0
    timeout_sec = (timeout_ms / 1000.0) if timeout_ms > 0 else None

    wf_log = get_paper_logger(init_state)
    ur = user_request.strip()
    wf_log.info(
        f"[PaperWF] workflow_start event=workflow_start "
        f"user_request_len={len(ur)} timeout_ms={timeout_ms} "
        f"human_confirm={config.paper_search_human_confirm_enabled}"
    )

    async def _runner() -> None:
        nonlocal final_out
        pl = get_paper_logger(init_state)
        t0 = time.monotonic()
        workflow_ok = True
        try:
            if timeout_sec is not None:
                final_out = await asyncio.wait_for(
                    graph.ainvoke(init_state),
                    timeout=timeout_sec,
                )
            else:
                final_out = await graph.ainvoke(init_state)
            if final_out and workflow_ok:
                workflow_ok = not is_paper_workflow_failed_state(final_out)
        except asyncio.TimeoutError:
            workflow_ok = False
            pl.exception(
                f"[PaperWF] workflow_timeout event=workflow_timeout node=workflow message=论文工作流执行超时"
            )
            await event_queue.put(
                {
                    "type": "error",
                    "data": {
                        "node": "workflow",
                        "message": "论文工作流执行超时",
                        "run_id": run_id,
                    },
                }
            )
        except PaperNodeError:
            workflow_ok = False
            pl.warning("[PaperWF] workflow_halted event=paper_node_error node=workflow")
        except Exception as e:
            workflow_ok = False
            pl.exception(f"[PaperWF] workflow_failed event=workflow_error node=workflow detail={e!r}")
            await event_queue.put(
                {
                    "type": "error",
                    "data": {
                        "node": "workflow",
                        "message": str(e),
                        "run_id": run_id,
                    },
                }
            )
        finally:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            errs = final_out.get("errors") or []
            pl.info(
                f"[PaperWF] workflow_end event=workflow_end ok={workflow_ok} "
                f"elapsed_ms={elapsed_ms:.0f} "
                f"final_report_path={final_out.get('final_report_path')!r} "
                f"error_count={len(errs)}"
            )
            await event_queue.put(
                {
                    "type": "done",
                    "data": {
                        "run_id": run_id,
                        "workspace_dir": str(ws),
                        "final_report_path": final_out.get("final_report_path"),
                        "errors": final_out.get("errors"),
                        "ok": workflow_ok,
                        "workflow_failed": bool(final_out.get("workflow_failed")),
                        "fallback_answer": final_out.get("fallback_answer"),
                    },
                }
            )

    task = asyncio.create_task(_runner())
    try:
        while True:
            msg = await event_queue.get()
            yield msg
            if msg.get("type") == "done":
                break
    finally:
        await task
        if config.paper_search_human_confirm_enabled:
            unregister_run(run_id)
        clear_rag_request_context()
