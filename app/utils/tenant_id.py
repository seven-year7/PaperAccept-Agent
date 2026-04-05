"""
/**
 * @Module: app/utils/tenant_id.py
 * @Description: RAG 多租户模拟：规范化 tenant_id 供 Milvus metadata 与布尔表达式使用，避免注入。
 * @Interface: normalize_tenant_id / build_milvus_tenant_expr
 */
"""

from __future__ import annotations

import hashlib
from typing import Optional

from loguru import logger

_ALLOWED_TENANT_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)
_MAX_LEN = 128


def normalize_tenant_id(raw: Optional[str]) -> str:
    """
    空或仅空白 -> default；白名单且长度合法则原样；否则 SHA256 十六进制（expr 安全）。
    # @Security: 非白名单统一哈希，避免 Milvus expr 注入与异常字符。
    """
    text = (raw or "").strip() or "default"
    if len(text) <= _MAX_LEN and all(c in _ALLOWED_TENANT_CHARS for c in text):
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    logger.info(f"[INFO][TENANT]: tenant_id 已规范化哈希 raw_len={len(text)}")
    return digest


def build_milvus_tenant_expr(normalized_tenant_id: str) -> str:
    """构造 Milvus JSON 字段过滤表达式（值已规范化，仍对引号反斜杠转义）。"""
    value = (normalized_tenant_id or "default").replace("\\", "\\\\").replace('"', '\\"')
    return f'metadata["tenant_id"] == "{value}"'
