"""
/**
 * @Module: scripts/paper_arxiv_smoke.py
 * @Description: 直连 PaperSearcher 验证 PyPI arxiv 客户端与网络；不经过 FastAPI 与 LLM。
 * @Interface: python scripts/paper_arxiv_smoke.py [--query ...] [--max-results N]
 */
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# 保证从项目根导入 app（与 uvicorn 工作目录一致）
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.agent.paper.schemas import StructuredArxivQuery  # noqa: E402
from app.tools.paper_arxiv_tool import PaperSearcher  # noqa: E402


async def _run(*, query: str, max_results: int | None) -> int:
    # @Step: 1 - 构造与 search 节点一致的规范化路径（normalize 在 PaperSearcher 内）
    structured = StructuredArxivQuery(querys=[query.strip()] if query.strip() else ["machine learning"])
    searcher = PaperSearcher(max_results=max_results) if max_results is not None else PaperSearcher()
    papers = await searcher.search(structured)
    n = len(papers)
    print(f"[INFO][PaperArxivSmoke]: paper_count={n}")
    if n == 0:
        print("[WARN][PaperArxivSmoke]: 未返回论文（查询过严或 arXiv 空结果）")
        return 1
    first = papers[0]
    print(f"[INFO][PaperArxivSmoke]: first arxiv_id={first.arxiv_id!r} title={first.title[:120]!r}...")
    print("[OK] paper_arxiv_smoke passed")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="直连 PaperSearcher 烟测 arXiv 检索")
    parser.add_argument(
        "--query",
        default="retrieval augmented generation",
        help="单条关键词短语（写入 StructuredArxivQuery.querys）",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="覆盖 PAPER_ARXIV_MAX_RESULTS（默认读 .env / config）",
    )
    args = parser.parse_args()
    max_results = args.max_results if args.max_results is not None else None
    code = asyncio.run(_run(query=args.query, max_results=max_results))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
