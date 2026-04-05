"""对话接口

提供基于 RAG Agent 的普通对话和流式对话接口
"""

import json

from fastapi import APIRouter, HTTPException
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.config import config
from app.models.request import ChatRequest, ClearRequest
from app.models.response import ApiResponse, SessionInfoResponse
from app.services.chat_intent_router import resolve_chat_intent
from app.services.paper_workflow_service import run_paper_research_stream
from app.services.rag_agent_service import rag_agent_service

router = APIRouter()


def _format_rag_stream_chunk(chunk: dict) -> dict | None:
    """将 rag_agent_service 的单条 chunk 转为 SSE 负载；不识别的类型返回 None。"""
    chunk_type = chunk.get("type", "unknown")
    chunk_data = chunk.get("data", None)

    if chunk_type == "debug":
        return {
            "event": "message",
            "data": json.dumps(
                {
                    "type": "debug",
                    "node": chunk.get("node", "unknown"),
                    "message_type": chunk.get("message_type", "unknown"),
                },
                ensure_ascii=False,
            ),
        }
    if chunk_type == "tool_call":
        return {
            "event": "message",
            "data": json.dumps({"type": "tool_call", "data": chunk_data}, ensure_ascii=False),
        }
    if chunk_type == "search_results":
        return {
            "event": "message",
            "data": json.dumps({"type": "search_results", "data": chunk_data}, ensure_ascii=False),
        }
    if chunk_type == "content":
        return {
            "event": "message",
            "data": json.dumps({"type": "content", "data": chunk_data}, ensure_ascii=False),
        }
    if chunk_type == "complete":
        return {
            "event": "message",
            "data": json.dumps({"type": "done", "data": chunk_data}, ensure_ascii=False),
        }
    if chunk_type == "error":
        return {
            "event": "message",
            "data": json.dumps({"type": "error", "data": str(chunk_data)}, ensure_ascii=False),
        }
    return None


@router.post("/chat")
async def chat(request: ChatRequest):
    """快速对话接口
    {
        "code": 200,
        "message": "success",
        "data": {
            "success": true,
            "answer": "回答内容",
            "errorMessage": null
        }
    }

    当开启 CHAT_PAPER_ROUTE_ENABLED 且路由为论文整图时，不执行工作流，返回 needsStream 提示改用 /api/chat_stream。

    Args:
        request: 对话请求

    Returns:
        统一格式的对话响应
    """
    try:
        logger.info(f"[会话 {request.id}] 收到快速对话请求: {request.question}")

        if config.chat_paper_route_enabled:
            routed = await resolve_chat_intent(
                request.question,
                force_route=request.force_route,
            )
            if routed.branch == "paper_workflow":
                hint = (
                    "已识别为论文整图调研需求；请使用 POST /api/chat_stream 提交相同请求体以获取 "
                    "SSE 进度（首条事件 type 为 route，后续与 /api/paper/research_stream 一致）。"
                )
                logger.info(f"[会话 {request.id}] 非流式命中论文路由，返回 needsStream 提示")
                return {
                    "code": 200,
                    "message": "success",
                    "data": {
                        "success": True,
                        "answer": hint,
                        "needsStream": True,
                        "branch": "paper_workflow",
                        "hint": hint,
                        "errorMessage": None,
                    },
                }

        answer = await rag_agent_service.query(
            request.question,
            session_id=request.id,
            user_id=request.user_id,
            tenant_id=request.tenant_id,
        )

        logger.info(f"[会话 {request.id}] 快速对话完成")

        data_ok: dict = {
            "success": True,
            "answer": answer,
            "errorMessage": None,
        }
        if config.chat_paper_route_enabled:
            data_ok["needsStream"] = False

        return {
            "code": 200,
            "message": "success",
            "data": data_ok,
        }

    except Exception as e:
        logger.error(f"对话接口错误: {e}")
        data_err: dict = {
            "success": False,
            "answer": None,
            "errorMessage": str(e),
        }
        if config.chat_paper_route_enabled:
            data_err["needsStream"] = False
        return {
            "code": 500,
            "message": "error",
            "data": data_err,
        }


@router.post("/chat_stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（基于 RAG Agent，SSE）

    返回 SSE 格式，data 字段为 JSON：

    当 CHAT_PAPER_ROUTE_ENABLED=true 时，首条为路由事件：
    data: {"type":"route","data":{"branch":"rag_chat"|"paper_workflow","confidence":...,"source":"rule"|"llm"|...,"intent":"general_rag"|"paper_workflow"}}

    论文分支后续事件与 POST /api/paper/research_stream 相同（顶层 type: phase、content、done 等）。

    RAG 分支：工具调用、content、done 等同原协议。

    Args:
        request: 对话请求

    Returns:
        SSE 事件流
    """
    logger.info(f"[会话 {request.id}] 收到流式对话请求: {request.question}")

    async def event_generator():
        try:
            if config.chat_paper_route_enabled:
                routed = await resolve_chat_intent(
                    request.question,
                    force_route=request.force_route,
                )
                route_envelope = {
                    "type": "route",
                    "data": {
                        "branch": routed.branch,
                        "confidence": routed.confidence,
                        "source": routed.source,
                        "intent": routed.intent,
                    },
                }
                yield {
                    "event": "message",
                    "data": json.dumps(route_envelope, ensure_ascii=False),
                }

                if routed.branch == "paper_workflow":
                    user_request = routed.effective_user_request(request.question)
                    async for payload in run_paper_research_stream(
                        user_request=user_request,
                        session_id=request.id,
                        tenant_id=request.tenant_id,
                    ):
                        yield {
                            "event": "message",
                            "data": json.dumps(payload, ensure_ascii=False),
                        }
                    logger.info(f"[会话 {request.id}] 论文工作流 SSE 完成")
                    return

            async for chunk in rag_agent_service.query_stream(
                request.question,
                session_id=request.id,
                user_id=request.user_id,
                tenant_id=request.tenant_id,
            ):
                formatted = _format_rag_stream_chunk(chunk)
                if formatted is not None:
                    yield formatted

            logger.info(f"[会话 {request.id}] 流式对话完成")

        except Exception as e:
            logger.error(f"流式对话接口错误: {e}")
            yield {
                "event": "message",
                "data": json.dumps(
                    {"type": "error", "data": str(e)},
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat/clear", response_model=ApiResponse)
async def clear_session(request: ClearRequest):
    """清空会话历史

    Args:
        request: 清空请求

    Returns:
        操作结果
    """
    try:
        success = await rag_agent_service.clear_session(request.session_id)
        logger.info(f"清空会话: {request.session_id}, 结果: {success}")

        return ApiResponse(
            status="success" if success else "error",
            message="会话已清空" if success else "清空会话失败",
            data=None,
        )

    except Exception as e:
        logger.error(f"清空会话错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/session/{session_id}", response_model=SessionInfoResponse)
async def get_session_info(session_id: str) -> SessionInfoResponse:
    """查询会话历史

    Args:
        session_id: 会话 ID

    Returns:
        会话信息
    """
    try:
        history = await rag_agent_service.get_session_history(session_id)

        return SessionInfoResponse(
            session_id=session_id,
            message_count=len(history),
            history=history,
        )

    except Exception as e:
        logger.error(f"获取会话信息错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
