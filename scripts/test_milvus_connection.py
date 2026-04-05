"""
/**
 * @Module: scripts/test_milvus_connection.py
 * @Description: 从项目根 .env 读取 MILVUS_HOST/PORT 等，调用 milvus_manager.connect() 并校验 biz collection 可访问（与 FastAPI lifespan 一致）。
 * @Interface: python scripts/test_milvus_connection.py [--keep-alive]
 */
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.config import config  # noqa: E402
from app.core.milvus_client import milvus_manager  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="烟测 Milvus 连接与 biz collection")
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="成功后不断开连接（默认会 disconnect，避免影响后续在同进程内的其它测试）",
    )
    args = parser.parse_args()

    host = config.milvus_host
    port = config.milvus_port
    name = milvus_manager.COLLECTION_NAME
    dim = milvus_manager.VECTOR_DIM

    print(f"[INFO] Milvus 目标: {host}:{port}")
    print(f"[INFO] collection={name!r} 期望向量维度={dim}")

    try:
        milvus_manager.connect()
    except Exception as e:
        print(f"[ERROR] connect() 失败: {e}", file=sys.stderr)
        print(
            "[HINT] 请确认 Milvus 已启动（如 docker compose -f vector-database.yml up），"
            "且 .env 中 MILVUS_HOST / MILVUS_PORT 正确。",
            file=sys.stderr,
        )
        return 1

    try:
        col = milvus_manager.get_collection()
        num = col.num_entities
    except Exception as e:
        print(f"[ERROR] get_collection() 或读取 num_entities 失败: {e}", file=sys.stderr)
        if not args.keep_alive:
            milvus_manager.close()
        return 1

    ok = milvus_manager.health_check()
    print(f"[OK] 已连接；collection {name!r} 实体数 num_entities={num}")
    if not ok:
        print("[WARN] health_check() 返回 False，但 connect/get_collection 已成功。", file=sys.stderr)

    if not args.keep_alive:
        milvus_manager.close()
        print("[INFO] 已调用 milvus_manager.close()（进程内单例已断开）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
