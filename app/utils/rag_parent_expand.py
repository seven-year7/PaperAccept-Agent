"""
/**
 * @Module: app/utils/rag_parent_expand.py
 * @Description: 混合/向量融合后的子块结果按 parent_id 去重，正文换为父块全文。
 * @Interface: expand_fusion_results_to_parents
 */
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from loguru import logger

from app.config import config

if TYPE_CHECKING:
    from app.services.vector_search_service import SearchResult


def expand_fusion_results_to_parents(results: List["SearchResult"]) -> List["SearchResult"]:
    """
    在子块检索/融合结果上，按 parent_id 去重，content 换为 parent_text。
    仅当 rag_hierarchical_chunks_enabled 且命中行含 parent_id + parent_text 时生效；否则原样返回。
    score 保留子块距离（门控应在调用方基于展开前的子结果计算）。
    """
    from app.services.vector_search_service import SearchResult

    if not config.rag_hierarchical_chunks_enabled or not results:
        return results

    seen: set[str] = set()
    out: List[SearchResult] = []
    for r in results:
        md = dict(r.metadata or {})
        pid = md.get("parent_id")
        ptext = md.get("parent_text")
        if not pid or not (isinstance(ptext, str) and ptext.strip()):
            out.append(r)
            if len(out) >= config.rag_top_k:
                break
            continue
        key = str(pid)
        if key in seen:
            continue
        seen.add(key)
        md["_child_hit_id"] = str(r.id)
        out.append(
            SearchResult(
                id=r.id,
                content=str(ptext),
                score=r.score,
                metadata=md,
            )
        )
        if len(out) >= config.rag_top_k:
            break

    if seen and len(out) < len(results):
        logger.debug(
            f"[DEBUG][RAG_PARENT_EXPAND]: raw_hits={len(results)} unique_parents={len(out)} "
            f"top_k_cap={config.rag_top_k}"
        )
    return out if out else results
