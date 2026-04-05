"""
/**
 * @Module: app/tools/long_term_memory_tool.py
 * @Description: 将用户确认的长期事实写入全局双 MD 之一；user_id 仅写入 meta 与日志审计。
 * @Interface: append_long_term_memory
 */
"""

from typing import Literal

from langchain_core.tools import tool
from loguru import logger

from app.config import config
from app.services.long_term_memory_store import append_memory_entry
from app.utils.rag_request_context import get_rag_request_context


@tool
def append_long_term_memory(
    memory_kind: Literal["user_profile", "agent_rules"],
    content: str,
    source: Literal["explicit", "inferred"] = "explicit",
    confidence: float = 1.0,
) -> str:
    """将内容追加到全局长期记忆：`agent_rules`→Agent.md，`user_profile`→Memory.md（目录见 LONG_TERM_MEMORY_BASE_PATH）。

    注意：只有**调用本工具**才会写磁盘；仅口头回复「已记住」不会落盘。
    仅在用户明确要求“记住/保存”或已明确确认的事实上使用。
    memory_kind:
      - user_profile: 用户身份、偏好、长期事实
      - agent_rules: 用户希望助手遵守的输出与行为约束
    source/confidence 供后续扩展；当前仅允许 source=explicit。

    Args:
        memory_kind: 写入 user_profile 或 agent_rules
        content: 要追加的简洁条目（勿包含密钥、令牌）
        source: explicit（默认）或 inferred（当前将被拒绝）
        confidence: 0~1，默认 1.0
    """
    if not config.long_term_memory_enabled:
        return "[LTM] 长期记忆读取已关闭（long_term_memory_enabled），工具未开放写入。"

    if not config.long_term_memory_write_enabled:
        return (
            "[LTM] 写入开关为 false（long_term_memory_write_enabled）："
            "未注册本工具时不应被调用；若仍出现请重启进程并检查 .env。"
        )

    ctx = get_rag_request_context() or {}
    user_id = str(ctx.get("user_id") or "").strip() or "default"

    if confidence < 0 or confidence > 1:
        logger.warning(f"[WARN][LTM_TOOL]: confidence 越界，已夹取: {confidence}")
        confidence = max(0.0, min(1.0, float(confidence)))

    result = append_memory_entry(
        user_id,
        memory_kind,
        content,
        source=source,
        confidence=confidence,
    )
    logger.info(f"[INFO][LTM_TOOL]: memory_kind={memory_kind} user_id={user_id} result={result!r}")
    return result
