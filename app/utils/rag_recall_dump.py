"""
/**
 * @Module: app/utils/rag_recall_dump.py
 * @Description: 将单次 RAG 召回的全文追加落盘到 Markdown（与对话 format_docs 一致 + 逐条正文）。
 * @Interface: append_recall_markdown
 */
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.documents import Document
from loguru import logger

from app.config import config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_write_lock = threading.Lock()


def _resolved_dump_path() -> Path:
    raw = (config.rag_recall_dump_md_path or "docx/rag_recall_runtime.md").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def format_bm25_section_lines(
    *,
    bm25_candidates: List[Dict[str, Any]],
    hybrid_obs: Dict[str, Any],
    title_heading: str = "###",
) -> List[str]:
    """ES(BM25) 融合前全量候选的 Markdown 行（供落盘与 dump 脚本复用）。"""
    lines: list[str] = []
    # 标题以 BM25 开头，便于在 md 里 Ctrl+F（搜 es/bm25 都能命中）
    lines.append(f"{title_heading} BM25 / ES 全量候选（Elasticsearch 融合前，按相关度排名）")
    lines.append("")
    if not config.rag_hybrid_enabled:
        lines.append("*当前 `RAG_HYBRID_ENABLED=false`，未执行独立 ES 召回列表。*")
        lines.append("")
        return lines
    if hybrid_obs.get("es_degraded"):
        lines.append("*本次 ES 不可用或未配置 URL，BM25 候选为空。*")
        lines.append("")
        return lines
    if not bm25_candidates:
        lines.append("*ES 已查询但返回 0 条。*")
        lines.append("")
        return lines
    lines.append(f"*共 {len(bm25_candidates)} 条（上限由 `RAG_HYBRID_BM25_TOP_K` 决定）。*")
    lines.append("")
    sub = "####" if title_heading.startswith("###") else "###"
    for rank, row in enumerate(bm25_candidates, start=1):
        md = dict(row.get("metadata") or {})
        lines.append(f"{sub} BM25 候选 {rank}")
        lines.append("")
        lines.append(f"- **chunk_id**: {row.get('id', '')}")
        lines.append(f"- **bm25_score**: {row.get('score', '')}")
        lines.append(f"- **_file_name**: {md.get('_file_name', md.get('file_name', ''))}")
        lines.append(f"- **_source**: {md.get('_source', md.get('source', ''))}")
        lines.append("")
        lines.append("**正文**:")
        lines.append("")
        lines.append("```")
        lines.append(str(row.get("content") or ""))
        lines.append("```")
        lines.append("")
    return lines


def append_recall_markdown(
    *,
    query: str,
    request_id: str,
    session_id: str,
    rag_tenant_id: str,
    below_threshold: bool,
    hybrid_obs: Dict[str, Any],
    bm25_candidates: List[Dict[str, Any]],
    context_for_model: str,
    docs: List[Document],
) -> None:
    # @Step: 1 - 开关与空文档则跳过
    if not config.rag_recall_dump_md_enabled:
        return
    if not docs:
        return

    path = _resolved_dump_path()
    lines: list[str] = []
    lines.append("---")
    lines.append("")
    lines.append(f"## RAG 召回实录")
    lines.append("")
    lines.append(f"- **UTC**: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"- **request_id**: {request_id}")
    lines.append(f"- **session_id**: {session_id}")
    lines.append(f"- **tenant_id**: {rag_tenant_id}")
    lines.append(f"- **retrieve_query**: {query}")
    lines.append(f"- **below_threshold**（低置信门控）: {below_threshold}")
    lines.append(f"- **RAG_HYBRID_ENABLED**: {config.rag_hybrid_enabled}")
    lines.append(f"- **RAG_HIERARCHICAL_CHUNKS_ENABLED**: {config.rag_hierarchical_chunks_enabled}")
    if hybrid_obs:
        lines.append(
            f"- **hybrid**: vec_hits={hybrid_obs.get('vec_hits')} "
            f"bm25_hits={hybrid_obs.get('bm25_hits')} es_degraded={hybrid_obs.get('es_degraded')}"
        )
    lines.append("")
    lines.append("### 模型侧上下文（format_docs，融合后 top_k）")
    lines.append("")
    lines.append("```text")
    lines.append(context_for_model)
    lines.append("```")
    lines.append("")
    lines.extend(
        format_bm25_section_lines(
            bm25_candidates=bm25_candidates,
            hybrid_obs=hybrid_obs,
            title_heading="###",
        )
    )
    lines.append("### 融合后条目（含向量 / BM25 来源标注）")
    lines.append("")
    for i, doc in enumerate(docs, start=1):
        md = dict(doc.metadata or {})
        lines.append(f"#### 融合后条目 {i}")
        lines.append("")
        lines.append(f"- **_chunk_id**: {md.get('_chunk_id', '')}")
        lines.append(f"- **_retrieve_source**: {md.get('_retrieve_source', '')}")
        if "_distance" in md:
            lines.append(f"- **L2**: {md.get('_distance')}")
        lines.append(f"- **_file_name**: {md.get('_file_name', md.get('file_name', ''))}")
        lines.append("")
        lines.append("**正文**:")
        lines.append("")
        lines.append("```")
        lines.append(doc.page_content or "")
        lines.append("```")
        lines.append("")

    block = "\n".join(lines) + "\n"
    nbytes: int = 0
    try:
        with _write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fp:
                fp.write(block)
                nbytes = len(block.encode("utf-8"))
        logger.info(
            f"[INFO][RAG_RECALL_DUMP]: 已追加召回全文 path={path} bytes={nbytes} "
            f"merged_chunks={len(docs)} bm25_candidates={len(bm25_candidates)} "
            f"below_threshold={below_threshold}"
        )
    except OSError as e:
        logger.warning(f"[WARN][RAG_RECALL_DUMP]: 写入失败 path={path} err={e}")
