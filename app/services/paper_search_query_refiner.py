"""
/**
 * @Module: app/services/paper_search_query_refiner.py
 * @Description: 检索确认阶段：根据用户自然语言说明修订 StructuredArxivQuery（小模型结构化输出）。
 * @Interface: refine_structured_with_adjustment_text
 */
"""

from __future__ import annotations

from textwrap import dedent
from typing import Any, Protocol, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.agent.paper.schemas import StructuredArxivQuery, normalize_structured_arxiv_query
from app.config import config


class _PaperWorkflowLog(Protocol):
    def warning(self, msg: str) -> None: ...


def _refiner_model_name() -> str:
    m = (config.paper_search_refiner_model or "").strip()
    return m if m else config.rag_summary_model


async def refine_structured_with_adjustment_text(
    structured: StructuredArxivQuery,
    adjustment_text: str,
    *,
    paper_log: _PaperWorkflowLog,
) -> StructuredArxivQuery:
    """
    将用户对检索条件的自然语言修改说明合并进当前结构化查询。
    无 API Key 或异常时返回原 structured 并打 WARN。
    """
    # @Step: 1 - 在 apply_confirmation_to_structured 之前调用；显式表单字段后于本结果再覆盖
    text = (adjustment_text or "").strip()
    if not text:
        return structured
    if not (config.openrouter_api_key or "").strip():
        paper_log.warning(
            "[WARN][PaperRefiner]: skip_refiner reason=no_openrouter_api_key"
        )
        return structured

    try:
        llm = ChatOpenAI(
            model=_refiner_model_name(),
            api_key=cast(Any, config.openrouter_api_key),
            base_url=config.openrouter_api_base,
            temperature=0.0,
            streaming=False,
        )
        structured_llm = llm.with_structured_output(StructuredArxivQuery)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    dedent(
                        """
                        你是 arXiv 检索条件修订器。根据「当前结构化检索条件」和「用户的修改说明」，输出**完整**新的 StructuredArxivQuery。
                        - 尊重用户意图：如限定时间、改关键词、加作者/标题/分类、改为按时间排序等。
                        - 用户未提及的字段尽量保留当前值；若说明要求「清空某字段」则置空字符串或空列表。
                        - querys 优先英文短语；2～5 条；与 search 节点规则一致。
                        仅输出结构化字段，不要解释。
                        """
                    ).strip(),
                ),
                (
                    "human",
                    "当前条件（JSON）：\n{current_json}\n\n用户修改说明：\n{adjustment}",
                ),
            ]
        )
        chain = prompt | structured_llm
        out = cast(
            StructuredArxivQuery,
            await chain.ainvoke(
                {
                    "current_json": structured.model_dump_json(ensure_ascii=False),
                    "adjustment": text,
                }
            ),
        )
        return normalize_structured_arxiv_query(out)
    except Exception as e:
        paper_log.warning(
            f"[WARN][PaperRefiner]: refiner_failed fallback=keep_original detail={e!r}"
        )
        return structured
