"""
/**
 * @Module: app/services/elasticsearch_chunk_store.py
 * @Description: RAG 知识块 Elasticsearch 索引（BM25），与 Milvus 同 chunk_id 双写；支持按 source 删除与租户过滤检索。
 * @Interface: ElasticsearchChunkStore.bulk_upsert / delete_by_source / search_bm25 / ping
 */
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from langchain_core.documents import Document
from loguru import logger

from app.config import config
from app.utils.log_preview import preview_for_log
from app.utils.tenant_id import normalize_tenant_id

_INDEX_MAPPINGS: Dict[str, Any] = {
    "properties": {
        "chunk_id": {"type": "keyword"},
        "tenant_id": {"type": "keyword"},
        "content": {"type": "text"},
        "source": {"type": "keyword", "ignore_above": 8190},
        "file_name": {"type": "keyword", "ignore_above": 512},
        "meta_json": {"type": "text", "index": False},
    }
}


class ElasticsearchChunkStore:
    """Elasticsearch 文档块存储（BM25 检索）"""

    def __init__(self) -> None:
        self._client: Optional[Elasticsearch] = None
        self._lock = threading.Lock()
        self._index_ensured = False

    def _should_use(self) -> bool:
        if not config.rag_hybrid_enabled:
            return False
        return bool((config.elasticsearch_url or "").strip())

    def _build_client(self) -> Optional[Elasticsearch]:
        url = (config.elasticsearch_url or "").strip()
        if not url:
            return None
        kwargs: Dict[str, Any] = {
            "request_timeout": max(1.0, float(config.rag_elasticsearch_timeout_ms) / 1000.0),
        }

        ca_raw = (config.elasticsearch_ca_certs or "").strip()
        ca_path: Optional[Path] = None
        if ca_raw:
            ca_candidate = Path(ca_raw)
            if not ca_candidate.is_absolute():
                ca_candidate = Path.cwd() / ca_candidate
            if ca_candidate.is_file():
                ca_path = ca_candidate.resolve()
            else:
                logger.warning(
                    f"[WARN][Elasticsearch]: ELASTICSEARCH_CA_CERTS 不是有效文件路径: {ca_raw} "
                    f"(已解析为 {ca_candidate})，将回退到仅 verify_certs 配置"
                )

        fp_raw = (config.elasticsearch_ssl_assert_fingerprint or "").strip()
        if fp_raw:
            kwargs["ssl_assert_fingerprint"] = fp_raw

        if ca_path is not None:
            # @Agent_Logic: 使用自建 CA / PEM 链时保持 verify_certs=True，真正解决自签名信任问题
            kwargs["ca_certs"] = str(ca_path)
            kwargs["verify_certs"] = True
        elif fp_raw:
            kwargs["verify_certs"] = True
        else:
            kwargs["verify_certs"] = config.elasticsearch_verify_certs
            if not config.elasticsearch_verify_certs:
                kwargs["ssl_show_warn"] = False

        user = (config.elasticsearch_basic_auth_user or "").strip()
        password = (config.elasticsearch_basic_auth_password or "").strip()
        if user:
            kwargs["basic_auth"] = (user, password)
        return Elasticsearch(url, **kwargs)

    def client(self) -> Optional[Elasticsearch]:
        if not self._should_use():
            return None
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                self._client = self._build_client()
        return self._client

    def diagnostic_client(self) -> Optional[Elasticsearch]:
        """
        不与 RAG_HYBRID_ENABLED 挂钩；只要配置了 ELASTICSEARCH_URL 即按与应用相同的 TLS/CA/指纹/basic_auth 构建客户端。
        供 scripts 连通性自测。
        """
        return self._build_client()

    def ping(self) -> bool:
        """集群可达返回 True；未启用或未配置 URL 时返回 True（视为跳过）。"""
        if not self._should_use():
            return True
        cli = self.client()
        if cli is None:
            return False
        try:
            return bool(cli.ping())
        except Exception as e:
            logger.warning(f"[WARN][Elasticsearch]: ping 失败: {e}")
            return False

    def ensure_index(self) -> None:
        if not self._should_use():
            return
        cli = self.client()
        if cli is None:
            return
        with self._lock:
            if self._index_ensured:
                return
            index_name = config.elasticsearch_index
            try:
                if cli.indices.exists(index=index_name):
                    self._index_ensured = True
                    return
                cli.indices.create(index=index_name, mappings=_INDEX_MAPPINGS)
                logger.info(f"[INFO][Elasticsearch]: 已创建索引 index={index_name}")
            except Exception as e:
                logger.error(f"[ERROR][Elasticsearch]: 创建索引失败 index={index_name} err={e}")
                raise
            self._index_ensured = True

    def bulk_upsert(self, documents: List[Document], chunk_ids: List[str]) -> int:
        """
        批量写入/覆盖文档；_id 与 Milvus 主键一致。

        Returns:
            成功写入的条数（与 bulk 报告一致）
        """
        if not self._should_use():
            return 0
        if len(documents) != len(chunk_ids):
            raise ValueError("documents 与 chunk_ids 长度不一致")
        if not documents:
            return 0
        cli = self.client()
        if cli is None:
            return 0
        self.ensure_index()
        index_name = config.elasticsearch_index
        actions: List[Dict[str, Any]] = []
        for doc, cid in zip(documents, chunk_ids):
            meta = dict(doc.metadata) if doc.metadata else {}
            tenant = str(meta.get("tenant_id") or normalize_tenant_id("default"))
            source_path = str(meta.get("_source") or "")
            file_name = str(meta.get("_file_name") or "")
            meta_copy = {k: v for k, v in meta.items() if isinstance(v, (str, int, float, bool, type(None)))}
            try:
                meta_json = json.dumps(meta_copy, ensure_ascii=False)
            except (TypeError, ValueError):
                meta_json = "{}"
            actions.append(
                {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": cid,
                    "_source": {
                        "chunk_id": cid,
                        "tenant_id": tenant,
                        "content": doc.page_content or "",
                        "source": source_path,
                        "file_name": file_name,
                        "meta_json": meta_json,
                    },
                }
            )
        try:
            ok, errors = bulk(cli, actions, refresh="wait_for", raise_on_error=False)
            if errors:
                logger.error(f"[ERROR][Elasticsearch]: bulk 部分失败 errors={errors[:3]}...")
            logger.info(f"[INFO][Elasticsearch]: bulk_upsert ok={ok} index={index_name}")
            return int(ok)
        except Exception as e:
            logger.error(f"[ERROR][Elasticsearch]: bulk_upsert 失败: {e}")
            raise

    def delete_by_source(self, source_path: str) -> int:
        """删除指定来源路径下的所有块（与 Milvus metadata['_source'] 一致）。"""
        if not self._should_use():
            return 0
        cli = self.client()
        if cli is None:
            return 0
        self.ensure_index()
        index_name = config.elasticsearch_index
        body = {"query": {"term": {"source": source_path}}}
        try:
            resp = cli.delete_by_query(
                index=index_name,
                body=body,
                refresh=True,
                request_timeout=max(1.0, float(config.rag_elasticsearch_timeout_ms) / 1000.0),
            )
            deleted = int(resp.get("deleted", 0) or 0)
            logger.info(f"[INFO][Elasticsearch]: delete_by_source source={source_path} deleted={deleted}")
            return deleted
        except Exception as e:
            logger.warning(f"[WARN][Elasticsearch]: delete_by_source 失败 source={source_path} err={e}")
            return 0

    def search_bm25(
        self,
        query: str,
        tenant_id: Optional[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        BM25 检索。

        Returns:
            每项含 id, content, score, metadata(反序列化自 meta_json 及 ES 字段)
        """
        if not self._should_use():
            return []
        cli = self.client()
        if cli is None:
            return []
        self.ensure_index()
        index_name = config.elasticsearch_index
        bool_query: Dict[str, Any] = {"must": [{"match": {"content": {"query": query}}}]}
        if config.rag_tenant_isolation_enabled:
            norm = normalize_tenant_id(tenant_id)
            bool_query["filter"] = [{"term": {"tenant_id": norm}}]
        body = {
            "query": {"bool": bool_query},
            "size": max(1, top_k),
            "_source": ["chunk_id", "content", "tenant_id", "source", "file_name", "meta_json"],
        }
        try:
            resp = cli.search(
                index=index_name,
                body=body,
                request_timeout=max(1.0, float(config.rag_elasticsearch_timeout_ms) / 1000.0),
            )
        except Exception as e:
            logger.warning(f"[WARN][Elasticsearch]: search_bm25 失败: {e}")
            raise
        out: List[Dict[str, Any]] = []
        for hit in resp.get("hits", {}).get("hits", []):
            src = hit.get("_source") or {}
            cid = str(src.get("chunk_id") or hit.get("_id") or "")
            meta: Dict[str, Any] = {}
            raw_meta = src.get("meta_json")
            if isinstance(raw_meta, str) and raw_meta.strip():
                try:
                    parsed = json.loads(raw_meta)
                    if isinstance(parsed, dict):
                        meta.update(parsed)
                except json.JSONDecodeError:
                    pass
            meta.setdefault("_source", src.get("source"))
            meta.setdefault("_file_name", src.get("file_name"))
            meta.setdefault("tenant_id", src.get("tenant_id"))
            meta["_bm25_score"] = float(hit.get("_score") or 0.0)
            out.append(
                {
                    "id": cid,
                    "content": str(src.get("content") or ""),
                    "score": float(hit.get("_score") or 0.0),
                    "metadata": meta,
                }
            )
        # @Step: BM25 召回明细（可选，便于对照 ES 命中与 RRF）
        if config.rag_hybrid_recall_detail_log:
            norm_t = normalize_tenant_id(tenant_id)
            logger.info(
                f"[INFO][RAG_BM25_RECALL] summary query={json.dumps(query, ensure_ascii=False)} "
                f"tenant_id={norm_t} index={index_name} bm25_hits={len(out)}"
            )
            for rank, row in enumerate(out, start=1):
                md = row.get("metadata") or {}
                payload = {
                    "phase": "bm25_raw",
                    "rank": rank,
                    "chunk_id": row.get("id"),
                    "bm25_score": row.get("score"),
                    "source": md.get("_source"),
                    "file_name": md.get("_file_name"),
                    "tenant_id": md.get("tenant_id"),
                    "content_preview": preview_for_log(str(row.get("content") or "")),
                }
                logger.info(f"[INFO][RAG_BM25_RECALL] {json.dumps(payload, ensure_ascii=False)}")
        return out


elasticsearch_chunk_store = ElasticsearchChunkStore()
