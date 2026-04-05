"""
/**
 * @Module: app/tools/knowledge_tool.py
 * @Description: 知识检索工具（Milvus 向量检索）+ 阈值门控 + 结构化观测，减少“假 RAG”。
 * @Interface: retrieve_knowledge
 */
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Dict, List, Tuple

from langchain_core.documents import Document
from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.services.vector_search_service import vector_search_service
from app.utils.rag_parent_expand import expand_fusion_results_to_parents
from app.utils.rag_recall_dump import append_recall_markdown
from app.utils.rag_request_context import get_rag_request_context
from app.utils.tenant_id import normalize_tenant_id


def _build_degraded_payload(
    request_id: str,
    session_id: str,
    query: str,
    reason: str,
    stage: str,
    elapsed_ms: float,
) -> Tuple[str, List[Document]]:
    """构造统一降级返回，确保主流程可继续。"""
    advice = (
        "请先给出通用排查建议，并提示用户稍后重试知识库检索或补充更多上下文。"
        if config.rag_degrade_general_advice_enabled
        else "请明确说明当前依据不足。"
    )
    degraded_content = (
        "【检索降级】当前知识库暂不可用，先给通用建议。\n"
        f"- degraded=true\n- reason={reason}\n- stage={stage}\n- elapsed_ms={elapsed_ms:.2f}\n"
        f"- request_id={request_id}\n- session_id={session_id}\n"
        "你不得声称“已经检索到可靠资料”。"
        f"{advice}"
    )
    degraded_doc = Document(
        page_content=degraded_content,
        metadata={
            "_degraded": True,
            "_reason": reason,
            "_stage": stage,
            "_elapsed_ms": round(elapsed_ms, 2),
            "_request_id": request_id,
            "_session_id": session_id,
            "_query": query,
        },
    )
    return degraded_content, [degraded_doc]


def _retrieve_core(query: str, tenant_id: str = "") -> Dict[str, Any]:
    """执行检索主逻辑，不含外层总超时控制。"""
    phase_start = time.perf_counter()
    hybrid_obs: Dict[str, Any] = {}
    bm25_candidates: List[Dict[str, Any]] = []
    if config.rag_hybrid_enabled:
        results, hybrid_obs, bm25_candidates = vector_search_service.hybrid_search_documents(
            query=query,
            tenant_id=tenant_id or None,
        )
    else:
        results = vector_search_service.search_similar_documents(
            query=query,
            top_k=config.rag_top_k,
            search_timeout_ms=config.rag_milvus_search_timeout_ms,
            tenant_id=tenant_id or None,
        )
    search_elapsed_ms = (time.perf_counter() - phase_start) * 1000

    # 门控与子距离：在父展开之前用「子块」结果计算（与向量/BM25 打分一致）
    # 仅向量路 L2 参与距离阈值；纯 BM25 命中无 _retrieve_source==vector 时不计入
    distances: List[float] = []
    for r in results:
        md = r.metadata or {}
        if md.get("_retrieve_source") == "bm25":
            continue
        distances.append(float(r.score))

    top1_distance = distances[0] if distances else None
    gap_12 = (distances[1] - distances[0]) if len(distances) >= 2 else None
    avg_distance = (sum(distances) / len(distances)) if distances else None

    if not distances:
        below_threshold = False
    else:
        abs_ok = top1_distance is not None and top1_distance <= float(config.rag_retrieve_max_distance)
        rel_ok = gap_12 is not None and gap_12 >= float(config.rag_retrieve_min_gap)
        avg_ok = avg_distance is not None and avg_distance <= float(config.rag_retrieve_max_avg_distance)
        below_threshold = not bool(abs_ok and rel_ok and avg_ok)

    results = expand_fusion_results_to_parents(results)
    chunk_count = len(results)

    docs: List[Document] = []
    for r in results:
        metadata = dict(r.metadata or {})
        metadata["_chunk_id"] = str(r.id)
        if metadata.get("_retrieve_source") == "bm25":
            metadata.pop("_distance", None)
        else:
            metadata["_distance"] = float(r.score)
        metadata["_degraded"] = False
        docs.append(Document(page_content=str(r.content), metadata=metadata))

    return {
        "docs": docs,
        "distances": distances,
        "chunk_count": chunk_count,
        "top1_distance": top1_distance,
        "gap_12": gap_12,
        "avg_distance": avg_distance,
        "below_threshold": below_threshold,
        "search_elapsed_ms": search_elapsed_ms,
        "hybrid_obs": hybrid_obs,
        "bm25_candidates": bm25_candidates,
    }


@tool(response_format="content_and_artifact")
def retrieve_knowledge(query: str) -> Tuple[str, List[Document]]:
    """从知识库中检索相关信息来回答问题
    
    当用户的问题涉及专业知识、文档内容或需要参考资料时，使用此工具。
    
    Args:
        query: 用户的问题或查询
        
    Returns:
        Tuple[str, List[Document]]: (格式化的上下文文本, 原始文档列表)
    """
    started = time.perf_counter()
    req_ctx = get_rag_request_context() or {}
    request_id = str(req_ctx.get("request_id") or "")
    session_id = str(req_ctx.get("session_id") or "")
    tenant_raw = str(req_ctx.get("tenant_id") or "")
    rag_tenant_id = normalize_tenant_id(tenant_raw)
    obs: Dict[str, Any] = {
        "request_id": request_id,
        "session_id": session_id,
        "retrieve_called": True,
        "retrieve_query": query,
        "is_rag_path": True,
        "rag_tenant_id": rag_tenant_id,
        "rag_tenant_isolation_enabled": config.rag_tenant_isolation_enabled,
    }
    try:
        logger.info(
            f"[INFO][RAG_RETRIEVE]: retrieve_knowledge called request_id={request_id} session_id={session_id} "
            f"rag_tenant_id={rag_tenant_id} query='{query}'"
        )

        # @Step: 1 - 外层工具超时（Fail-safe）
        # @Agent_Logic: 避免检索链路阻塞主流程；超时统一降级，不抛到顶层。
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_retrieve_core, query, tenant_raw)
            try:
                core = future.result(timeout=config.rag_retrieve_tool_timeout_ms / 1000)
            except FutureTimeoutError:
                elapsed_ms = (time.perf_counter() - started) * 1000
                obs.update(
                    {
                        "degraded": True,
                        "reason": "timeout",
                        "stage": "tool",
                        "elapsed_ms": round(elapsed_ms, 2),
                        "chunk_count": 0,
                        "distances": [],
                        "top1_distance": None,
                        "gap_12": None,
                        "below_threshold": None,
                    }
                )
                content, artifacts = _build_degraded_payload(
                    request_id=request_id,
                    session_id=session_id,
                    query=query,
                    reason="timeout",
                    stage="tool",
                    elapsed_ms=elapsed_ms,
                )
                logger.warning(
                    f"[WARN][RAG_RETRIEVE]: timeout request_id={request_id} session_id={session_id} "
                    f"elapsed_ms={elapsed_ms:.2f}"
                )
                if config.rag_observability_enabled:
                    logger.info(f"[INFO][RAG_OBS]: {json.dumps(obs, ensure_ascii=False)}")
                return content, artifacts

        docs = core["docs"]
        bm25_candidates = list(core.get("bm25_candidates") or [])
        distances = core["distances"]
        chunk_count = core["chunk_count"]
        top1_distance = core["top1_distance"]
        gap_12 = core["gap_12"]
        avg_distance = core["avg_distance"]
        below_threshold = core["below_threshold"]
        elapsed_ms = (time.perf_counter() - started) * 1000
        hybrid_obs = dict(core.get("hybrid_obs") or {})
        obs.update(
            {
                "degraded": False,
                "reason": "",
                "stage": "none",
                "elapsed_ms": round(elapsed_ms, 2),
                "chunk_count": chunk_count,
                "distances": distances,
                "top1_distance": top1_distance,
                "gap_12": gap_12,
                "avg_distance": avg_distance,
                "below_threshold": below_threshold,
                "thresholds": {
                    "max_distance": float(config.rag_retrieve_max_distance),
                    "min_gap": float(config.rag_retrieve_min_gap),
                    "max_avg_distance": float(config.rag_retrieve_max_avg_distance),
                },
                "milvus_timeout_ms": int(config.rag_milvus_search_timeout_ms),
                "elasticsearch_timeout_ms": int(config.rag_elasticsearch_timeout_ms),
                "tool_timeout_ms": int(config.rag_retrieve_tool_timeout_ms),
                "rag_hybrid_enabled": bool(config.rag_hybrid_enabled),
                "hybrid_vec_hits": hybrid_obs.get("vec_hits"),
                "hybrid_bm25_hits": hybrid_obs.get("bm25_hits"),
                "hybrid_es_degraded": hybrid_obs.get("es_degraded"),
                "rag_hierarchical_chunks_enabled": bool(config.rag_hierarchical_chunks_enabled),
            }
        )
        if config.rag_observability_enabled:
            logger.info(f"[INFO][RAG_OBS]: {json.dumps(obs, ensure_ascii=False)}")

        if not docs:
            logger.warning(
                f"[WARN][RAG_RETRIEVE]: no_docs request_id={request_id} session_id={session_id} query='{query}'"
            )
            return "【检索结论】库中无可靠依据：未检索到相关资料。请不要编造，建议向用户澄清问题或说明需要更多上下文。", []

        if below_threshold:
            reason = (
                f"top1_distance={top1_distance}, gap_12={gap_12}, avg_distance={avg_distance}, "
                f"thresholds(max_distance={config.rag_retrieve_max_distance}, "
                f"min_gap={config.rag_retrieve_min_gap}, max_avg_distance={config.rag_retrieve_max_avg_distance})"
            )
            append_recall_markdown(
                query=query,
                request_id=request_id,
                session_id=session_id,
                rag_tenant_id=rag_tenant_id,
                below_threshold=True,
                hybrid_obs=hybrid_obs,
                bm25_candidates=bm25_candidates,
                context_for_model=format_docs(docs),
                docs=docs,
            )
            return (
                "【检索结论】库中无可靠依据（低置信命中）。\n"
                f"- 观测: {reason}\n"
                "你必须明确告知用户“知识库中没有可靠依据支撑确定结论”，不得把不确定内容当作事实陈述；"
                "优先提出澄清问题或建议用户提供文档/日志/指标等可检索材料。",
                docs,
            )

        context = format_docs(docs)
        append_recall_markdown(
            query=query,
            request_id=request_id,
            session_id=session_id,
            rag_tenant_id=rag_tenant_id,
            below_threshold=False,
            hybrid_obs=hybrid_obs,
            bm25_candidates=bm25_candidates,
            context_for_model=context,
            docs=docs,
        )
        logger.info(
            f"[INFO][RAG_RETRIEVE]: hit request_id={request_id} session_id={session_id} chunk_count={len(docs)}"
        )
        return context, docs
        
    except Exception as e:
        elapsed_ms = (time.perf_counter() - started) * 1000
        error_text = str(e).lower()
        if "timeout" in error_text or "timed out" in error_text:
            reason = "timeout"
            stage = "milvus_search"
        elif "连接" in str(e) or "connect" in error_text or "unavailable" in error_text:
            reason = "unavailable"
            stage = "milvus_search"
        else:
            reason = "error"
            stage = "unknown"
        obs.update(
            {
                "degraded": True,
                "reason": reason,
                "stage": stage,
                "elapsed_ms": round(elapsed_ms, 2),
                "chunk_count": 0,
                "distances": [],
                "top1_distance": None,
                "gap_12": None,
                "below_threshold": None,
            }
        )
        logger.error(f"知识检索工具调用失败: {e}")
        if config.rag_observability_enabled:
            logger.info(f"[INFO][RAG_OBS]: {json.dumps(obs, ensure_ascii=False)}")
        return _build_degraded_payload(
            request_id=request_id,
            session_id=session_id,
            query=query,
            reason=reason,
            stage=stage,
            elapsed_ms=elapsed_ms,
        )


def format_docs(docs: List[Document]) -> str:
    """
    格式化文档列表为上下文文本
    
    Args:
        docs: 文档列表
        
    Returns:
        str: 格式化的上下文文本
    """
    formatted_parts = []
    
    for i, doc in enumerate(docs, 1):
        # 提取元数据
        metadata = doc.metadata
        source = metadata.get("_file_name", "未知来源")
        distance = metadata.get("_distance", None)
        
        # 提取标题信息 (如果有)
        headers = []
        for key in ["h1", "h2", "h3"]:
            if key in metadata and metadata[key]:
                headers.append(metadata[key])
        
        header_str = " > ".join(headers) if headers else ""
        
        # 构建格式化文本
        formatted = f"【参考资料 {i}】"
        if header_str:
            formatted += f"\n标题: {header_str}"
        formatted += f"\n来源: {source}"
        if distance is not None:
            formatted += f"\n距离(L2): {distance}"
        formatted += f"\n内容:\n{doc.page_content}\n"
        
        formatted_parts.append(formatted)
    
    return "\n".join(formatted_parts)
