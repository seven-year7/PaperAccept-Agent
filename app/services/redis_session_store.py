"""
/**
 * @Module: app/services/redis_session_store.py
 * @Description: Redis Hash 会话存储（history_jsonl 事件流），用于 RAG 对话的会话持久化与可观测。
 * @Interface: RedisSessionStore.get_events / append_events / clear
 */
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from loguru import logger
from redis.asyncio import Redis

from app.config import config


@dataclass(frozen=True)
class SessionEvent:
    """会话事件（可读、可演进）"""

    id: str
    ts: int
    role: str
    content: str
    name: Optional[str] = None
    call_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "ts": self.ts,
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            payload["name"] = self.name
        if self.call_id:
            payload["call_id"] = self.call_id
        if self.meta:
            payload["meta"] = self.meta
        return payload


class RedisSessionStore:
    """Redis Hash 会话存储（history_jsonl + meta）"""

    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Optional[Redis] = None

    async def _get_client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"rag:session:{session_id}"

    async def _refresh_ttl(self, client: Redis, key: str) -> None:
        """刷新会话 TTL，保持会话字段生命周期一致。"""
        await client.expire(key, int(config.rag_session_ttl_seconds))

    async def get_events(self, session_id: str) -> List[Dict[str, Any]]:
        """读取会话事件列表（按写入顺序）"""
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            history_jsonl = await client.hget(key, "history_jsonl")
            if not history_jsonl:
                return []
        except Exception as e:
            logger.error(f"[ERROR][RedisSession]: 读取会话失败 session={session_id} err={type(e).__name__}: {e}")
            return []

        events: List[Dict[str, Any]] = []
        for line in history_jsonl.splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    events.append(obj)
            except Exception as e:
                logger.warning(f"[WARN][RedisSession]: 解析 JSONL 失败 session={session_id} err={e}")
                continue
        return events

    async def append_events(self, session_id: str, new_events: List[Dict[str, Any]]) -> None:
        """追加事件并刷新 TTL；会执行裁剪（按条数）"""
        if not new_events:
            return

        try:
            client = await self._get_client()
            key = self._session_key(session_id)

            # 读取旧历史（单写入者假设下可接受）
            old_events = await self.get_events(session_id)
            merged = old_events + new_events

            # 裁剪最近 N 条（含 tool/tool_result）
            max_events = max(1, int(config.rag_session_max_events))
            if len(merged) > max_events:
                merged = merged[-max_events:]

            history_jsonl = "\n".join(json.dumps(e, ensure_ascii=False) for e in merged)

            now_ts = int(time.time())
            meta = {
                "schema_version": "1",
                "updated_at": str(now_ts),
                "ttl_seconds": str(int(config.rag_session_ttl_seconds)),
                "message_count": str(len(merged)),
            }

            # created_at 仅首次写入
            created_at = await client.hget(key, "created_at")
            if not created_at:
                meta["created_at"] = str(now_ts)

            last_event = merged[-1] if merged else None
            if isinstance(last_event, dict):
                meta["last_role"] = str(last_event.get("role", ""))
                last_content = str(last_event.get("content", ""))
                meta["last_preview"] = last_content[:200]

            await client.hset(key, mapping={"history_jsonl": history_jsonl, **meta})
            await self._refresh_ttl(client, key)

            logger.info(
                f"[INFO][RedisSession]: 写入会话事件 session={session_id} "
                f"append={len(new_events)} total={len(merged)} ttl={config.rag_session_ttl_seconds}s"
            )
        except Exception as e:
            logger.error(f"[ERROR][RedisSession]: 写入会话失败 session={session_id} err={type(e).__name__}: {e}")
            return

    async def get_summary(self, session_id: str) -> str:
        """读取会话滚动摘要。"""
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            summary = await client.hget(key, "conversation_summary")
            return str(summary or "")
        except Exception as e:
            logger.error(
                f"[ERROR][RedisSession]: 读取会话摘要失败 session={session_id} err={type(e).__name__}: {e}"
            )
            return ""

    async def save_summary(
        self,
        session_id: str,
        summary_text: str,
        rounds_count: int,
        updated_at: int | None = None,
    ) -> None:
        """保存会话滚动摘要及相关元信息。"""
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            now_ts = int(updated_at or time.time())
            await client.hset(
                key,
                mapping={
                    "conversation_summary": summary_text,
                    "summary_round_count": str(int(rounds_count)),
                    "summary_updated_at": str(now_ts),
                },
            )
            await self._refresh_ttl(client, key)
        except Exception as e:
            logger.error(
                f"[ERROR][RedisSession]: 写入会话摘要失败 session={session_id} err={type(e).__name__}: {e}"
            )

    async def get_round_count(self, session_id: str) -> int:
        """读取会话轮数计数。"""
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            val = await client.hget(key, "round_count")
            return int(val) if val is not None else 0
        except Exception as e:
            logger.error(
                f"[ERROR][RedisSession]: 读取轮次失败 session={session_id} err={type(e).__name__}: {e}"
            )
            return 0

    async def incr_round_count(self, session_id: str, delta: int = 1) -> int:
        """自增会话轮次并返回新值。"""
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            new_count = await client.hincrby(key, "round_count", int(delta))
            await self._refresh_ttl(client, key)
            return int(new_count)
        except Exception as e:
            logger.error(
                f"[ERROR][RedisSession]: 自增轮次失败 session={session_id} err={type(e).__name__}: {e}"
            )
            return 0

    async def clear(self, session_id: str) -> bool:
        try:
            client = await self._get_client()
            key = self._session_key(session_id)
            deleted = await client.delete(key)
            return deleted > 0
        except Exception as e:
            logger.error(f"[ERROR][RedisSession]: 清空会话失败 session={session_id} err={type(e).__name__}: {e}")
            return False

    # helpers
    @staticmethod
    def new_event(
        *,
        role: str,
        content: str,
        name: Optional[str] = None,
        call_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ev = SessionEvent(
            id=str(uuid.uuid4()),
            ts=int(time.time()),
            role=role,
            content=content,
            name=name,
            call_id=call_id,
            meta=meta,
        )
        return ev.to_dict()


# 全局单例（按需初始化连接）
redis_session_store = RedisSessionStore(config.redis_url)

