"""
/**
 * @Module: scripts/test_redis_session_store.py
 * @Description: Redis 会话存储连通性与读写自检脚本（PING + HSET/HGET/EXPIRE）。
 * @Interface: main()
 */
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict

import redis


def _print_kv(k: str, v: Any) -> None:
    print(f"{k}={v}")


def main() -> int:
    # @Step: 1 - 读取配置
    # @Agent_Logic: 尽量与应用配置一致，优先使用环境变量 REDIS_URL。
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    session_id = os.getenv("TEST_SESSION_ID", f"test_{int(time.time())}")
    key = f"rag:session:{session_id}"

    print("== Redis Session Store Self-Test ==")
    _print_kv("redis_url", redis_url)
    _print_kv("session_id", session_id)
    _print_kv("key", key)
    print()

    # @Step: 2 - 建立连接 + ping
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        pong = r.ping()
        _print_kv("ping", pong)
    except Exception as e:
        print("[ERROR] Redis 连接失败：")
        print(f"  type={type(e).__name__}")
        print(f"  err={e}")
        print()
        print("排查建议：")
        print("- 确认 Redis 进程已启动并监听端口（默认 6379）")
        print("- 确认 REDIS_URL 正确（若 Redis 在 Docker/WSL/远程机，localhost 可能不对）")
        print("- Windows 防火墙/安全软件是否拦截 6379")
        return 2

    # @Step: 3 - 写入一条最小会话（HSET + EXPIRE）
    now = int(time.time())
    event: Dict[str, Any] = {
        "id": "evt-1",
        "ts": now,
        "role": "user",
        "content": "hello",
    }
    history_jsonl = str(event).replace("'", '"')  # 简单可读，避免额外 json import

    mapping = {
        "schema_version": "1",
        "created_at": str(now),
        "updated_at": str(now),
        "ttl_seconds": "60",
        "message_count": "1",
        "last_role": "user",
        "last_preview": "hello",
        "history_jsonl": history_jsonl,
    }

    try:
        hset_count = r.hset(key, mapping=mapping)
        expire_ok = r.expire(key, 60)
        _print_kv("hset_fields_written", hset_count)
        _print_kv("expire_ok", expire_ok)
    except Exception as e:
        print("[ERROR] Redis 写入失败：")
        print(f"  type={type(e).__name__}")
        print(f"  err={e}")
        return 3

    # @Step: 4 - 读取校验（HGETALL）
    try:
        data = r.hgetall(key)
        print()
        print("== HGETALL result (truncated) ==")
        for k2 in sorted(data.keys()):
            v2 = data[k2]
            if len(v2) > 200:
                v2 = v2[:200] + "...(truncated)"
            print(f"{k2}: {v2}")
        ttl = r.ttl(key)
        print()
        _print_kv("ttl_seconds", ttl)
    except Exception as e:
        print("[ERROR] Redis 读取失败：")
        print(f"  type={type(e).__name__}")
        print(f"  err={e}")
        return 4

    print()
    print("[OK] Redis 会话存储读写正常。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

