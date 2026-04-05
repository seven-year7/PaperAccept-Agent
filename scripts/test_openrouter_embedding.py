"""
/**
 * @Module: scripts/test_openrouter_embedding.py
 * @Description: 烟测 OpenRouter OpenAI 兼容 embeddings API 是否与 .env 中模型/密钥配置一致（与 vector_embedding_service 同参）。
 * @Interface: python scripts/test_openrouter_embedding.py [--text "..."]
 */
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from openai import OpenAI  # noqa: E402

from app.config import config  # noqa: E402

# 与 app/services/vector_embedding_service.py 中单例保持一致
_EMBED_DIM = 1024


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 OpenRouter 嵌入 API")
    parser.add_argument(
        "--text",
        default="embedding smoke test 中文探测",
        help="用于嵌入的短文本",
    )
    args = parser.parse_args()

    key = (config.openrouter_api_key or "").strip()
    if not key or key == "your-api-key-here":
        print(
            "[ERROR] 请在项目根 .env 设置 OPENROUTER_API_KEY（当前为空或占位符）。",
            file=sys.stderr,
        )
        return 1

    base = (config.openrouter_api_base or "").strip() or "https://openrouter.ai/api/v1"
    model = (config.openrouter_embedding_model or "").strip() or "openai/text-embedding-3-small"

    print(f"[INFO] base_url={base}")
    print(f"[INFO] model={model}")
    print(f"[INFO] dimensions={_EMBED_DIM}")
    print(f"[INFO] input_chars={len(args.text)}")

    client = OpenAI(api_key=key, base_url=base)
    try:
        response = client.embeddings.create(
            model=model,
            input=args.text,
            dimensions=_EMBED_DIM,
            encoding_format="float",
        )
    except Exception as e:
        print(f"[ERROR] embeddings.create 请求失败: {e}", file=sys.stderr)
        return 1

    data = getattr(response, "data", None)
    if data is None:
        err = getattr(response, "error", None)
        extra = f" provider_error={err!r}" if err else ""
        print(
            f"[ERROR] response.data 为 None（生产代码里会报 'NoneType' object is not subscriptable）。{extra}",
            file=sys.stderr,
        )
        print(f"[ERROR] 完整 response: {response!r}", file=sys.stderr)
        return 1
    if len(data) < 1:
        print(f"[ERROR] response.data 为空列表: {data!r}", file=sys.stderr)
        return 1

    first = data[0]
    emb = getattr(first, "embedding", None)
    if emb is None:
        print(f"[ERROR] data[0].embedding 缺失: {first!r}", file=sys.stderr)
        return 1

    n = len(emb)
    print(f"[OK] 嵌入维度={n}，前 3 维={emb[:3]}")
    if n != _EMBED_DIM:
        print(
            f"[WARN] 期望维度 {_EMBED_DIM}，实际 {n}；若 Milvus 建库维度固定，请与 OPENROUTER_EMBEDDING_MODEL / dimensions 对齐。",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
