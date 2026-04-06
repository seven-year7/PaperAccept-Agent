"""
/**
 * @Module: scripts/test_openrouter_chat.py
 * @Description: 烟测 OpenRouter（或兼容 OPENROUTER_API_BASE）的 Chat Completions，与 RagAgentService 共用 KEY / BASE / RAG_MODEL，用于排查 401「User not found」等鉴权问题。
 * @Interface: python scripts/test_openrouter_chat.py [--model MODEL] [--also-summary]
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


def _smoke_chat(
    client: OpenAI,
    *,
    model: str,
    label: str,
) -> int:
    # @Step: 1 - 最小非流式补全，与 LangChain ChatOpenAI 底层请求一致（同 key/base）
    # @Agent_Logic: 短回复降本；失败时把异常原样交给调用方打印
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": 'Reply with a single word only: "pong".',
                }
            ],
            max_tokens=32,
            temperature=0.0,
        )
    except Exception as e:
        print(f"[ERROR][OpenRouterChat:{label}] 请求失败: {e}", file=sys.stderr)
        err_name = type(e).__name__
        body = str(e)
        if "401" in body or "AuthenticationError" in err_name:
            print(
                "[INFO][OpenRouterChat]: 401 多为 OPENROUTER_API_KEY 无效、与 OPENROUTER_API_BASE 不匹配，"
                "或上游账号问题（日志里常见 User not found）。",
                file=sys.stderr,
            )
        return 1

    choice0 = (response.choices or [None])[0]
    msg = getattr(choice0, "message", None) if choice0 else None
    text = (getattr(msg, "content", None) or "").strip()
    if not text:
        print(
            f"[ERROR][OpenRouterChat:{label}] 返回空 content: {response!r}",
            file=sys.stderr,
        )
        return 1

    print(f"[OK][OpenRouterChat:{label}] model={model!r} reply={text!r}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="测试 OpenRouter 兼容 Chat Completions（与 RAG 对话同参）",
    )
    parser.add_argument(
        "--model",
        default="",
        help="覆盖 RAG_MODEL；默认使用 config.rag_model",
    )
    parser.add_argument(
        "--also-summary",
        action="store_true",
        help="额外用 RAG_SUMMARY_MODEL 再请求一次（摘要链路同 KEY）",
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
    model = (args.model or "").strip() or (config.rag_model or "").strip()
    if not model:
        print(
            "[ERROR] RAG_MODEL 为空且未传 --model；请在 .env 设置 RAG_MODEL 或传入 --model。",
            file=sys.stderr,
        )
        return 1

    print(f"[INFO][OpenRouterChat]: base_url={base}", flush=True)
    print(f"[INFO][OpenRouterChat]: rag_model={model!r}", flush=True)

    client = OpenAI(api_key=key, base_url=base)
    rc = _smoke_chat(client, model=model, label="rag_model")
    if rc != 0:
        return rc

    if args.also_summary:
        summary_model = (config.rag_summary_model or "").strip()
        if not summary_model:
            print(
                "[WARN][OpenRouterChat]: RAG_SUMMARY_MODEL 为空，跳过 --also-summary",
                file=sys.stderr,
            )
            return 0
        print(f"[INFO][OpenRouterChat]: rag_summary_model={summary_model!r}", flush=True)
        return _smoke_chat(client, model=summary_model, label="rag_summary_model")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
