"""
/**
 * @Module: app/api/paper.py
 * @Description: 论文多 Agent 工作流 HTTP 接口（SSE）。
 * @Interface: POST /api/paper/research_stream
 */
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.models.request import PaperResearchStreamRequest, PaperSearchConfirmRequest
from app.services.paper_search_confirm_registry import submit_search_confirmation
from app.services.paper_workflow_service import run_paper_research_stream
from app.utils.paper_workflow_logging import get_paper_logger

router = APIRouter()


@router.post("/paper/confirm_search")
async def paper_search_confirm(request: PaperSearchConfirmRequest):
    """在开启 PAPER_SEARCH_HUMAN_CONFIRM_ENABLED 时，对 search_confirm 事件中的结构化查询进行人工通过或覆盖。"""
    payload = {
        "run_id": request.run_id,
        "approved": request.approved,
        "querys": request.querys,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "title_phrase": request.title_phrase,
        "author": request.author,
        "categories": request.categories,
        "sort_mode": request.sort_mode,
        "adjustment_text": request.adjustment_text,
        "reason": request.reason,
    }
    pl = get_paper_logger(
        {
            "run_id": request.run_id,
            "session_id": "",
            "tenant_id": "",
        }
    )
    pl.info(
        f"[PaperWF] api_confirm_search event=api_confirm_search "
        f"approved={request.approved} has_querys_override={bool(request.querys)} "
        f"has_adjustment_text={bool((request.adjustment_text or '').strip())}"
    )
    if not submit_search_confirmation(request.run_id, payload):
        pl.warning("[PaperWF] api_confirm_search_reject event=confirm_not_applied reason=run_not_found_or_done")
        raise HTTPException(
            status_code=404,
            detail="run_id 不存在、已结束或已确认过",
        )
    return {"ok": True, "run_id": request.run_id}


@router.post("/paper/research_stream")
async def paper_research_stream(request: PaperResearchStreamRequest):
    """论文调研工作流 SSE。

    data 为 JSON，type 取值示例：phase、content、search_confirm（开启人工确认时先于 search_confirm 有一条 content 说明与 run_id）、assistant_message_boundary（仅人工确认路径：确认已应用后、arXiv 检索前一次，供前端拆助手气泡）、reading_progress、writing、error、done；失败路径含 phase.node=error_finalize 与兜底 content。
    主图节点含 `write`（嵌套子图）。子图内 phase.data.node：`writePlan`、`writeExecute`、`writeAudit`（全局 audit，OK/REVISE/REPLAN 后再整批 execute 或改纲）；子图结束后进入 `report`。
    """

    async def event_generator():
        api_log = get_paper_logger(
            {
                "run_id": "",
                "session_id": request.session_id,
                "tenant_id": request.tenant_id,
            }
        )
        api_log.info(
            f"[PaperWF] api_research_stream event=api_stream_open "
            f"user_request_len={len((request.user_request or '').strip())}"
        )
        try:
            async for payload in run_paper_research_stream(
                user_request=request.user_request,
                session_id=request.session_id,
                tenant_id=request.tenant_id,
            ):
                yield {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}
        except Exception as e:
            logger.exception("[ERROR][PaperAPI]: research_stream")
            err = json.dumps({"type": "error", "data": {"message": str(e)}}, ensure_ascii=False)
            yield {"event": "message", "data": err}

    return EventSourceResponse(event_generator())
