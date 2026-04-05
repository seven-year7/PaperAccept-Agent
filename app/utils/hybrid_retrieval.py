"""
/**
 * @Module: app/utils/hybrid_retrieval.py
 * @Description: Milvus 向量与 ES BM25 两路按排名加权融合（非等权 RRF），按 chunk_id 去重排序。
 * @Interface: weighted_hybrid_fusion_search_results
 */
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.vector_search_service import SearchResult


def weighted_hybrid_fusion_search_results(
    vec_results: List["SearchResult"],
    bm25_rows: List[Dict[str, Any]],
    *,
    rank_damping_k: int,
    vec_weight: float,
    bm25_weight: float,
    final_top_k: int,
) -> List["SearchResult"]:
    """
    两路按排名贡献加权求和：每路贡献为 weight * 1/(k+rank+1)，再按 chunk_id 累加后排序。

    # @Step: 1 - 向量路按 Milvus 返回顺序赋 rank，累加 vec_weight/(k+rank+1)
    # @Step: 2 - BM25 路同理，累加 bm25_weight/(k+rank+1)
    # @Agent_Logic: 相对等权 RRF，显式提高向量路占比（默认 0.7 / 0.3）以符合「语义为主、词面为辅」
    """
    from app.services.vector_search_service import SearchResult

    k = float(max(1, int(rank_damping_k)))
    wv = max(0.0, float(vec_weight))
    wb = max(0.0, float(bm25_weight))

    scores: Dict[str, float] = defaultdict(float)
    for rank, r in enumerate(vec_results):
        cid = str(r.id or "")
        if cid and wv > 0.0:
            scores[cid] += wv / (k + float(rank) + 1.0)
    for rank, row in enumerate(bm25_rows):
        cid = str(row.get("id") or "")
        if cid and wb > 0.0:
            scores[cid] += wb / (k + float(rank) + 1.0)

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    sorted_ids = sorted_ids[: max(1, final_top_k)]

    vec_map: Dict[str, SearchResult] = {str(r.id): r for r in vec_results if r.id}

    merged: List[SearchResult] = []
    for cid in sorted_ids:
        if cid in vec_map:
            vr = vec_map[cid]
            meta = dict(vr.metadata or {})
            fs = round(scores[cid], 6)
            meta["_fusion_score"] = fs
            meta["_rrf_score"] = fs  # 兼容旧日志字段名，实为加权融合分
            meta["_retrieve_source"] = "vector"
            merged.append(
                SearchResult(
                    id=vr.id,
                    content=vr.content,
                    score=vr.score,
                    metadata=meta,
                )
            )
            continue
        bm25_hit = next((x for x in bm25_rows if str(x.get("id")) == cid), None)
        if bm25_hit:
            meta = dict(bm25_hit.get("metadata") or {})
            fs = round(scores[cid], 6)
            meta["_fusion_score"] = fs
            meta["_rrf_score"] = fs
            meta["_bm25_score"] = float(bm25_hit.get("score") or 0.0)
            meta["_retrieve_source"] = "bm25"
            merged.append(
                SearchResult(
                    id=cid,
                    content=str(bm25_hit.get("content") or ""),
                    score=float(bm25_hit.get("score") or 0.0),
                    metadata=meta,
                )
            )
    return merged


def reciprocal_rank_fusion_search_results(
    vec_results: List["SearchResult"],
    bm25_rows: List[Dict[str, Any]],
    *,
    rrf_k: int,
    final_top_k: int,
) -> List["SearchResult"]:
    """兼容旧接口：等权两路（各 1.0）。"""
    return weighted_hybrid_fusion_search_results(
        vec_results,
        bm25_rows,
        rank_damping_k=rrf_k,
        vec_weight=1.0,
        bm25_weight=1.0,
        final_top_k=final_top_k,
    )
