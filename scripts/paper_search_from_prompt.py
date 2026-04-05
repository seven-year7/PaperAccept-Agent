"""
/**
 * @Module: scripts/paper_search_from_prompt.py
 * @Description: 与 search 节点一致：LLM 将自然语言转为 StructuredArxivQuery，再调用 PaperSearcher（需 OPENROUTER_API_KEY）。
 * @Interface: python scripts/paper_search_from_prompt.py [--max-results N]（默认用户句见 DEFAULT_USER_REQUEST）
 */
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from textwrap import dedent
from typing import cast

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from app.agent.paper.llm_utils import get_paper_chat_model  # noqa: E402
from app.agent.paper.schemas import (  # noqa: E402
    StructuredArxivQuery,
    normalize_structured_arxiv_query,
    paper_meta_to_search_result_record,
)
from app.tools.paper_arxiv_tool import PaperSearcher, preview_arxiv_search_query  # noqa: E402

_FALLBACK = ("machine learning", "deep learning", "neural network")

# 无命令行参数时使用（可直接改这里换默认检索意图）
DEFAULT_USER_REQUEST = "帮我检索最近一年的有关网络安全的论文"


async def run(*, user_request: str, max_results: int | None) -> int:
    try:
        llm = get_paper_chat_model(temperature=0.1, streaming=False)
        structured_llm = llm.with_structured_output(StructuredArxivQuery)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    dedent(
                        """
                        你是学术文献检索助手。将用户的自然语言需求转为 arXiv 检索参数。
                        - querys：2～5 条关键词短语，**优先使用英文**（arXiv 以英文为主）；若用户仅写中文，请给出对应英译或通用英文学术检索词。
                        - 用户明确「按论文标题找」时填写 title_phrase（优先英文短语）；明确「某作者」时填写 author（姓名，可含空格）。
                        - start_date / end_date：若用户明确时间范围则填 YYYY-MM-DD，否则留空字符串。
                        - sort_mode：用户强调「最新」「最近发表」「按时间」等填 submitted_date；否则填 relevance。
                        - categories：仅当用户明确学科/arxiv 分区时填写，如机器学习 cs.LG、人工智能 cs.AI；不确定则空列表。
                        仅输出结构化字段，不要解释。
                        """
                    ).strip(),
                ),
                ("human", "{user_request}"),
            ]
        )
        structured = cast(
            StructuredArxivQuery,
            await (prompt | structured_llm).ainvoke({"user_request": user_request}),
        )
    except Exception as e:
        print(f"[WARN] LLM 结构化失败，使用兜底: {e}", file=sys.stderr)
        structured = StructuredArxivQuery(querys=list(_FALLBACK))

    structured = normalize_structured_arxiv_query(structured)
    preview = preview_arxiv_search_query(structured)

    print("=== 结构化查询（LLM → StructuredArxivQuery）===")
    print(json.dumps(structured.model_dump(), ensure_ascii=False, indent=2))
    print("\n=== 实际发往 arXiv 的 query 预览 ===")
    print(preview)
    print()

    searcher = PaperSearcher(max_results=max_results) if max_results is not None else PaperSearcher()
    papers = await searcher.search(structured)

    records = [paper_meta_to_search_result_record(p) for p in papers]
    print(f"=== 返回论文数: {len(records)} ===")
    print("=== 论文列表（JSON：paper_id / title / authors / summary / published / category / categories / url）===")
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0 if papers else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="从自然语言跑论文 search 链路（LLM + arXiv）；不写参数时用脚本内写死的 DEFAULT_USER_REQUEST。",
        epilog=f"默认用户句: {DEFAULT_USER_REQUEST!r}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "prompt_pos",
        nargs="?",
        default="",
        metavar="PROMPT",
        help="覆盖默认需求；省略则使用脚本内 DEFAULT_USER_REQUEST",
    )
    parser.add_argument("--prompt", default="", help="与位置参数二选一")
    parser.add_argument("--max-results", type=int, default=None, help="覆盖 PAPER_ARXIV_MAX_RESULTS")
    args = parser.parse_args()
    prompt = (args.prompt or args.prompt_pos or "").strip() or DEFAULT_USER_REQUEST
    print(f"[INFO] 用户请求: {prompt[:200]}{'…' if len(prompt) > 200 else ''}\n")
    code = asyncio.run(run(user_request=prompt, max_results=args.max_results))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
