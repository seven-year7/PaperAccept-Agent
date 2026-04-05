"""向量检索服务模块"""

import json
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from pymilvus import Collection

from app.config import config
from app.core.milvus_client import milvus_manager
from app.services.vector_embedding_service import vector_embedding_service
from app.utils.log_preview import preview_for_log
from app.utils.tenant_id import build_milvus_tenant_expr, normalize_tenant_id


class SearchResult:
    """搜索结果类"""

    def __init__(
        self,
        id: str,
        content: str,
        score: float,
        metadata: Dict[str, Any],
    ):
        self.id = id
        self.content = content
        self.score = score
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }


class VectorSearchService:
    """向量检索服务 - 负责从 Milvus 中搜索相似向量"""

    def __init__(self):
        """初始化向量检索服务"""
        logger.info("向量检索服务初始化完成")

    def search_similar_documents(
        self,
        query: str,
        top_k: int = 3,
        search_timeout_ms: int | None = None,
        tenant_id: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        搜索相似文档

        Args:
            query: 查询文本
            top_k: 返回最相似的K个结果
            search_timeout_ms: Milvus 搜索超时（毫秒）
            tenant_id: 租户 ID（模拟）；开启 rag_tenant_isolation_enabled 时写入 Milvus expr 过滤

        Returns:
            List[SearchResult]: 搜索结果列表

        Raises:
            RuntimeError: 搜索失败时抛出
        """
        try:
            started = time.perf_counter()
            normalized_tenant = normalize_tenant_id(tenant_id)
            expr: str | None = None
            if config.rag_tenant_isolation_enabled:
                expr = build_milvus_tenant_expr(normalized_tenant)
            logger.info(
                f"开始搜索相似文档, 查询: {query}, topK: {top_k}, "
                f"search_timeout_ms={search_timeout_ms}, "
                f"tenant_isolation={config.rag_tenant_isolation_enabled}, "
                f"rag_tenant_id={normalized_tenant}"
            )

            # 1. 将查询文本向量化
            embed_started = time.perf_counter()
            query_vector = vector_embedding_service.embed_query(query)
            embed_elapsed_ms = (time.perf_counter() - embed_started) * 1000
            logger.debug(f"查询向量生成成功, 维度: {len(query_vector)}")

            # 2. 获取 collection
            collection: Collection = milvus_manager.get_collection()

            # 3. 构建搜索参数
            search_params = {
                "metric_type": "L2",  # 欧氏距离
                "params": {"nprobe": 10},
            }

            # 4. 执行搜索（可选按 metadata.tenant_id 预过滤）
            search_started = time.perf_counter()
            timeout_s = (search_timeout_ms / 1000) if search_timeout_ms else None
            search_kwargs: Dict[str, Any] = {
                "data": [query_vector],
                "anns_field": "vector",
                "param": search_params,
                "limit": top_k,
                "output_fields": ["id", "content", "metadata"],
                "timeout": timeout_s,
            }
            if expr:
                search_kwargs["expr"] = expr
            results = collection.search(**search_kwargs)
            search_elapsed_ms = (time.perf_counter() - search_started) * 1000

            # 5. 解析搜索结果
            search_results = []
            for hits in results:
                for hit in hits:
                    result = SearchResult(
                        id=hit.entity.get("id"),
                        content=hit.entity.get("content"),
                        score=hit.distance,  # L2 距离，越小越相似
                        metadata=hit.entity.get("metadata", {}),
                    )
                    search_results.append(result)

            total_elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                f"搜索完成, 找到 {len(search_results)} 个相似文档, "
                f"embed_elapsed_ms={embed_elapsed_ms:.2f}, search_elapsed_ms={search_elapsed_ms:.2f}, "
                f"total_elapsed_ms={total_elapsed_ms:.2f}"
            )
            return search_results

        except Exception as e:
            error_text = str(e).lower()
            if "timeout" in error_text or "timed out" in error_text:
                logger.warning(f"搜索相似文档超时: {e}")
                raise TimeoutError(f"milvus_search_timeout: {e}") from e
            logger.error(f"搜索相似文档失败: {e}")
            raise RuntimeError(f"搜索失败: {e}") from e

    def hybrid_search_documents(
        self,
        query: str,
        tenant_id: Optional[str] = None,
    ) -> tuple[List[SearchResult], Dict[str, Any], List[Dict[str, Any]]]:
        """
        Milvus ANN + Elasticsearch BM25，按排名加权融合为最终 ``rag_top_k`` 条
        （默认向量 0.7、BM25 0.3，公式 ``weight/(k+rank+1)`` 再累加）。

        ES 查询失败时降级为仅向量路参与融合（等价于仅向量排序）。

        Returns:
            (融合后结果, 观测字典, ES BM25 原始候选列表（融合前，供落盘对照；勿写入日志 JSON）)
        """
        from app.services.elasticsearch_chunk_store import elasticsearch_chunk_store
        from app.utils.hybrid_retrieval import weighted_hybrid_fusion_search_results

        obs: Dict[str, Any] = {
            "hybrid_enabled": True,
            "es_degraded": False,
            "vec_hits": 0,
            "bm25_hits": 0,
        }
        norm_tenant = normalize_tenant_id(tenant_id)
        logger.info(
            f"[INFO][HybridRAG]: 进入混合检索 Milvus(ANN)+ES(BM25)→加权融合 "
            f"query_preview={json.dumps(query[:80], ensure_ascii=False)} "
            f"vec_top_k={config.rag_hybrid_vec_top_k} bm25_top_k={config.rag_hybrid_bm25_top_k} "
            f"final_top_k={config.rag_top_k} tenant_id={norm_tenant}"
        )
        vec_results = self.search_similar_documents(
            query=query,
            top_k=config.rag_hybrid_vec_top_k,
            search_timeout_ms=config.rag_milvus_search_timeout_ms,
            tenant_id=tenant_id,
        )
        obs["vec_hits"] = len(vec_results)
        if config.rag_hybrid_recall_detail_log and vec_results:
            logger.info(
                f"[INFO][RAG_VEC_RECALL] summary query={json.dumps(query, ensure_ascii=False)} "
                f"tenant_id={norm_tenant} vec_top_k={config.rag_hybrid_vec_top_k} vec_hits={len(vec_results)}"
            )
            for rank, r in enumerate(vec_results, start=1):
                md = dict(r.metadata or {})
                payload = {
                    "phase": "vector_raw",
                    "rank": rank,
                    "chunk_id": str(r.id),
                    "l2_distance": float(r.score),
                    "source": md.get("_source") or md.get("source"),
                    "file_name": md.get("_file_name"),
                    "tenant_id": md.get("tenant_id"),
                    "content_preview": preview_for_log(str(r.content or "")),
                }
                logger.info(f"[INFO][RAG_VEC_RECALL] {json.dumps(payload, ensure_ascii=False)}")

        bm25_rows: List[Dict[str, Any]] = []
        if (config.elasticsearch_url or "").strip():
            try:
                bm25_rows = elasticsearch_chunk_store.search_bm25(
                    query=query,
                    tenant_id=tenant_id,
                    top_k=config.rag_hybrid_bm25_top_k,
                )
            except Exception as e:
                logger.warning(f"[WARN][HybridRAG]: ES 检索失败，降级为仅向量路: {e}")
                obs["es_degraded"] = True
        else:
            obs["es_degraded"] = True
            logger.warning("[WARN][HybridRAG]: RAG_HYBRID_ENABLED 但未配置 ELASTICSEARCH_URL，跳过 BM25")
        obs["bm25_hits"] = len(bm25_rows)
        logger.info(
            f"[INFO][HybridRAG]: 向量路+BM25 已召回，即将加权融合 "
            f"vec_hits={obs['vec_hits']} bm25_hits={obs['bm25_hits']} es_degraded={obs['es_degraded']}"
        )
        merged = weighted_hybrid_fusion_search_results(
            vec_results,
            bm25_rows,
            rank_damping_k=config.rag_hybrid_rrf_k,
            vec_weight=config.rag_hybrid_vec_weight,
            bm25_weight=config.rag_hybrid_bm25_weight,
            final_top_k=config.rag_top_k,
        )
        logger.info(
            f"[INFO][HybridRAG]: 加权融合完成 merged_count={len(merged)} "
            f"vec_w={config.rag_hybrid_vec_weight} bm25_w={config.rag_hybrid_bm25_weight}"
        )
        if config.rag_hybrid_recall_detail_log:
            logger.info(
                f"[INFO][RAG_RRF_RECALL] summary query={json.dumps(query, ensure_ascii=False)} "
                f"tenant_id={norm_tenant} rank_k={config.rag_hybrid_rrf_k} "
                f"vec_w={config.rag_hybrid_vec_weight} bm25_w={config.rag_hybrid_bm25_weight} "
                f"final_top_k={config.rag_top_k} merged_count={len(merged)} "
                f"vec_hits={obs['vec_hits']} bm25_hits={obs['bm25_hits']} es_degraded={obs['es_degraded']}"
            )
            for rank, r in enumerate(merged, start=1):
                md = dict(r.metadata or {})
                payload = {
                    "phase": "after_weighted_fusion",
                    "rank": rank,
                    "chunk_id": str(r.id),
                    "retrieve_source": md.get("_retrieve_source"),
                    "fusion_score": md.get("_fusion_score"),
                    "rrf_score": md.get("_rrf_score"),
                    "score_raw": float(r.score),
                    "score_meaning": "l2_distance_if_vector_else_bm25",
                    "source": md.get("_source"),
                    "file_name": md.get("_file_name"),
                    "content_preview": preview_for_log(str(r.content or "")),
                }
                logger.info(f"[INFO][RAG_RRF_RECALL] {json.dumps(payload, ensure_ascii=False)}")

        return merged, obs, bm25_rows


# 全局单例
vector_search_service = VectorSearchService()
