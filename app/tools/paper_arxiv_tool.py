"""
/**
 * @Module: app/tools/paper_arxiv_tool.py
 * @Description: 使用 PyPI `arxiv` 客户端检索元数据；供论文工作流与可选 RAG @tool 复用。
 * @Interface: PaperSearcher.search / search_arxiv_papers
 */
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, List, Tuple, cast

import arxiv
from langchain_core.tools import tool
from loguru import logger

from app.agent.paper.schemas import (
    ArxivSortMode,
    PaperMeta,
    StructuredArxivQuery,
    normalize_structured_arxiv_query,
)
from app.config import config
from app.utils.paper_workflow_logging import get_paper_logger_from_context
from app.utils.rag_request_context import get_rag_request_context

_TOOL_SUMMARY_MAX_CHARS = 4000


def _sanitize_token_for_arxiv_field(text: str) -> str:
    """ti/au/all 引号内文本：去掉双引号与换行，避免破坏 arXiv query 语法（后续若要保留精确短语可改为配对引号检测）。"""
    return (text or "").replace('"', " ").replace("\n", " ").strip()


def _date_to_arxiv(d: str, end_of_day: bool) -> str:
    """YYYY-MM-DD -> YYYYMMDDHHMM for arXiv submittedDate range."""
    d = (d or "").strip()
    if not d:
        return ""
    try:
        dt = datetime.strptime(d, "%Y-%m-%d")
        if end_of_day:
            return dt.strftime("%Y%m%d") + "2359"
        return dt.strftime("%Y%m%d") + "0000"
    except ValueError:
        return ""


def _build_search_query(structured: StructuredArxivQuery) -> str:
    """组合 ti:/au:/all: OR 与 submittedDate；调用方宜先 normalize_structured_arxiv_query。"""
    clauses: List[str] = []

    tp = (structured.title_phrase or "").strip()
    if tp:
        safe = _sanitize_token_for_arxiv_field(tp)
        clauses.append(f'ti:"{safe}"')

    au = (structured.author or "").strip()
    if au:
        safe = _sanitize_token_for_arxiv_field(au)
        clauses.append(f'au:"{safe}"')

    keyword_parts: List[str] = []
    for q in structured.querys or []:
        q = (q or "").strip()
        if q:
            safe = _sanitize_token_for_arxiv_field(q)
            keyword_parts.append(f'all:"{safe}"')
    if keyword_parts:
        clauses.append("(" + " OR ".join(keyword_parts) + ")")

    if not clauses:
        clauses.append('(all:"machine learning")')

    core = " AND ".join(clauses)

    if structured.categories:
        cat_block = "(" + " OR ".join(f"cat:{c}" for c in structured.categories) + ")"
        core = f"({cat_block}) AND ({core})"

    s = _date_to_arxiv(structured.start_date, end_of_day=False)
    e = _date_to_arxiv(structured.end_date, end_of_day=True)
    if s and e:
        date_part = f"submittedDate:[{s} TO {e}]"
        return f"{core} AND {date_part}"
    if s:
        date_part = f"submittedDate:[{s} TO 999912312359]"
        return f"{core} AND {date_part}"
    if e:
        date_part = f"submittedDate:[000001010000 TO {e}]"
        return f"{core} AND {date_part}"
    return core


def preview_arxiv_search_query(structured: StructuredArxivQuery) -> str:
    """规范化后生成与检索一致的 arXiv API query 字符串（供日志与调试）。"""
    return _build_search_query(normalize_structured_arxiv_query(structured))


def _arxiv_result_to_paper_meta(result: arxiv.Result) -> PaperMeta:
    # @Step: 1 - 与历史 PaperMeta 字段对齐（摘要截断防暴涨）
    short_id = (result.get_short_id() or "").strip()
    base_id = re.sub(r"v\d+$", "", short_id) if short_id else ""
    title = (result.title or "").replace("\n", " ").strip()
    authors = [a.name for a in (result.authors or []) if getattr(a, "name", None)]
    published = result.published.isoformat() if result.published else ""
    published_year = int(result.published.year) if result.published else None
    summary = (result.summary or "").strip()[:8000]
    pdf_url = getattr(result, "pdf_url", "") or ""
    abs_url = getattr(result, "entry_id", "") or ""
    primary_cat = (getattr(result, "primary_category", None) or "").strip()
    cats = [str(c).strip() for c in (getattr(result, "categories", None) or []) if str(c).strip()]
    return PaperMeta(
        arxiv_id=base_id or short_id,
        arxiv_short_id=short_id or base_id,
        title=title,
        authors=authors,
        published=published,
        published_year=published_year,
        summary=summary,
        pdf_url=pdf_url,
        abs_url=abs_url,
        primary_category=primary_cat,
        categories=cats,
    )


def _arxiv_sort_from_structured(structured: StructuredArxivQuery) -> Tuple[arxiv.SortCriterion, arxiv.SortOrder]:
    if structured.sort_mode == "submitted_date":
        return arxiv.SortCriterion.SubmittedDate, arxiv.SortOrder.Descending
    return arxiv.SortCriterion.Relevance, arxiv.SortOrder.Descending


def _sync_search_arxiv(
    search_query: str,
    max_results: int,
    sort_by: arxiv.SortCriterion,
    sort_order: arxiv.SortOrder,
    trace_run_id: str = "",
) -> List[PaperMeta]:
    """在线程中执行阻塞式 arxiv.Client 调用，带有限重试与线性退避。"""
    search = arxiv.Search(
        query=search_query,
        max_results=max_results,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    client = arxiv.Client()
    retries = max(1, int(config.paper_arxiv_max_retries or 1))
    backoff = float(config.paper_arxiv_retry_backoff_seconds or 2.0)
    last_exc: BaseException | None = None
    for attempt in range(retries):
        try:
            return [_arxiv_result_to_paper_meta(r) for r in client.results(search)]
        except Exception as e:
            last_exc = e
            wf = f" wf_run={trace_run_id}" if trace_run_id else ""
            logger.warning(
                f"[WARN][PaperSearcher]: arxiv results attempt {attempt + 1}/{retries} failed:{wf} detail={e!r}"
            )
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    raise RuntimeError(
        f"arxiv_fetch_failed after {retries} attempts: {last_exc}"
    ) from last_exc


class PaperSearcher:
    """arXiv 检索封装（arxiv PyPI）。"""

    def __init__(self, *, max_results: int | None = None, delay_seconds: float | None = None):
        self.max_results = max_results if max_results is not None else config.paper_arxiv_max_results
        self.delay_seconds = (
            delay_seconds if delay_seconds is not None else config.paper_arxiv_query_delay_seconds
        )

    async def search(self, structured: StructuredArxivQuery) -> List[PaperMeta]:
        structured = normalize_structured_arxiv_query(structured)
        sq = _build_search_query(structured)
        sort_by, sort_order = _arxiv_sort_from_structured(structured)
        ctx = get_rag_request_context() or {}
        trace_run_id = str(ctx.get("request_id") or "")
        pl = get_paper_logger_from_context()
        pl.info(
            f"[PaperWF] arxiv_search_start event=arxiv_query_built component=PaperSearcher "
            f"arxiv_query_preview={sq[:240]!r} max_results={self.max_results} "
            f"query_terms_count={len(structured.querys)} "
            f"ti={bool(structured.title_phrase)} au={bool(structured.author)} "
            f"sort={structured.sort_mode} cats={len(structured.categories)}"
        )
        await asyncio.sleep(self.delay_seconds)
        papers = await asyncio.to_thread(
            _sync_search_arxiv,
            sq,
            self.max_results,
            sort_by,
            sort_order,
            trace_run_id,
        )
        pl.info(
            f"[PaperWF] arxiv_search_done event=arxiv_results_ok component=PaperSearcher "
            f"paper_count={len(papers)}"
        )
        return papers


def _query_string_to_querys(query: str) -> List[str]:
    """将用户单行 query 拆成多条 OR 短语（逗号/分号/中文顿号）。"""
    raw = (query or "").strip()
    if not raw:
        return ["machine learning"]
    for sep in (";", "；", "，"):
        raw = raw.replace(sep, ",")
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts if parts else [raw[:200]]


def _papers_to_tool_payload(papers: List[PaperMeta]) -> List[dict[str, Any]]:
    rows: List[dict[str, Any]] = []
    for paper in papers:
        summary = (paper.summary or "")[:_TOOL_SUMMARY_MAX_CHARS]
        if len(paper.summary or "") > _TOOL_SUMMARY_MAX_CHARS:
            summary += "…"
        pc = (paper.primary_category or "").strip()
        if not pc and paper.categories:
            pc = paper.categories[0]
        rows.append(
            {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors[:20],
                "published": paper.published,
                "category": pc,
                "categories": paper.categories[:20],
                "summary_excerpt": summary,
                "pdf_url": paper.pdf_url,
                "abs_url": paper.abs_url,
            }
        )
    return rows


def _parse_tool_sort_mode(sort_mode: str) -> str:
    s = (sort_mode or "").strip().lower().replace(" ", "_")
    if s in ("submitted_date", "date", "latest", "recent"):
        return "submitted_date"
    return "relevance"


def _parse_tool_categories(categories: str) -> List[str]:
    raw = (categories or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
    return parts


@tool
async def search_arxiv_papers(
    query: str,
    start_date: str = "",
    end_date: str = "",
    sort_mode: str = "relevance",
    categories: str = "",
) -> str:
    """在 arXiv 上检索论文元数据（标题、作者、摘要节选、PDF/摘要页链接）。

    当用户需要查最新预印本、某方向的论文列表或 arXiv ID 相关信息时使用。
    请使用英文或中英文关键词；多个关键词可用英文逗号分隔。

    Args:
        query: 检索关键词或短语，多个概念用逗号分隔
        start_date: 可选，提交起始日期 YYYY-MM-DD
        end_date: 可选，提交结束日期 YYYY-MM-DD
        sort_mode: relevance（默认）或 submitted_date / latest / recent 表示按提交时间新到旧
        categories: 可选，arXiv 分类码逗号分隔，如 cs.LG,cs.AI

    Returns:
        JSON 字符串：论文列表字段含 arxiv_id、title、authors、published、category、categories、summary_excerpt（单条摘要节选最多约 4000 字符）、pdf_url、abs_url
    """
    tl = get_paper_logger_from_context()
    tl.info(
        f"[PaperWF] arxiv_tool_call event=search_arxiv_papers component=PaperArxivTool "
        f"query_preview={query[:120]!r}"
    )
    structured = normalize_structured_arxiv_query(
        StructuredArxivQuery(
            querys=_query_string_to_querys(query),
            start_date=(start_date or "").strip(),
            end_date=(end_date or "").strip(),
            sort_mode=cast(ArxivSortMode, _parse_tool_sort_mode(sort_mode)),
            categories=_parse_tool_categories(categories),
        )
    )
    papers = await PaperSearcher().search(structured)
    payload = _papers_to_tool_payload(papers)
    tl.info(
        f"[PaperWF] arxiv_tool_done event=search_arxiv_papers_end component=PaperArxivTool "
        f"count={len(payload)}"
    )
    return json.dumps({"count": len(payload), "papers": payload}, ensure_ascii=False)
