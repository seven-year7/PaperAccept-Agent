"""
/**
 * @Module: app/agent/paper/nodes/reading_node.py
 * @Description: 并行阅读论文摘要并结构化抽取，写入单份 Markdown。
 * @Interface: make_reading_agent_node
 */
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import Any, Awaitable, Callable, Dict, List

import aiofiles
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from app.utils.paper_workflow_logging import get_paper_logger

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.reading_sanitize import (
    format_reading_title_line,
    merge_reading_markdown_blocks,
    sanitize_reading_paragraph,
)
from app.agent.paper.schemas import PaperMeta, ReadingExtract, normalize_paper_dict_for_reading
from app.agent.paper.state import PaperWorkflowState
from app.config import config

_FALLBACK_PARAGRAPH = "摘要未涉及"


def _fallback_reading_extract() -> ReadingExtract:
    return ReadingExtract(
        core_problem=_FALLBACK_PARAGRAPH,
        key_methods=_FALLBACK_PARAGRAPH,
        innovation=_FALLBACK_PARAGRAPH,
        limitations=_FALLBACK_PARAGRAPH,
        contributions=_FALLBACK_PARAGRAPH,
    )


def _sanitize_extract(ex: ReadingExtract) -> ReadingExtract:
    return ReadingExtract(
        core_problem=sanitize_reading_paragraph(ex.core_problem),
        key_methods=sanitize_reading_paragraph(ex.key_methods),
        innovation=sanitize_reading_paragraph(ex.innovation),
        limitations=sanitize_reading_paragraph(ex.limitations),
        contributions=sanitize_reading_paragraph(ex.contributions),
    )


def _reading_block_from_extract(paper: PaperMeta, ex: ReadingExtract) -> str:
    title_line = format_reading_title_line(paper.title)
    ex = _sanitize_extract(ex)
    block = (
        f"## {paper.arxiv_id} — {title_line}\n\n"
        f"- 链接: {(paper.abs_url or '').strip()}\n\n"
        f"### 核心问题\n{ex.core_problem}\n\n"
        f"### 关键方法\n{ex.key_methods}\n\n"
        f"### 创新点\n{ex.innovation}\n\n"
        f"### 局限性\n{ex.limitations}\n\n"
        f"### 贡献\n{ex.contributions}\n\n---\n\n"
    )
    return block


def _placeholder_paper_block(arxiv_id: str, title: str, message: str) -> str:
    t = format_reading_title_line(title)
    msg = sanitize_reading_paragraph(message)
    return f"## {arxiv_id} — {t}\n\n> {msg}\n\n---\n\n"


def make_reading_agent_node(
    event_queue: asyncio.Queue,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    _file_lock = asyncio.Lock()

    async def _extract_one(paper: PaperMeta, pl) -> str:
        llm = get_paper_chat_model(temperature=0.2, streaming=False)
        structured = llm.with_structured_output(ReadingExtract)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    dedent(
                        """
                        你是论文阅读助手。仅根据给出的标题与摘要（可能截断）抽取要点，不要编造未出现的事实。
                        字段：core_problem、key_methods、innovation、limitations、contributions。
                        使用中文简练段落；若无信息则填「摘要未涉及」。
                        """
                    ).strip(),
                ),
                (
                    "human",
                    "标题: {title}\n作者: {authors}\n摘要:\n{summary}\n",
                ),
            ]
        )
        chain = prompt | structured
        summary_in = sanitize_reading_paragraph(paper.summary)[:12000]
        authors_line = ", ".join(paper.authors)
        try:
            raw_out = await chain.ainvoke(
                {
                    "title": paper.title,
                    "authors": authors_line,
                    "summary": summary_in,
                }
            )
        except Exception as e:
            pl.warning(
                f"[PaperWF] reading_extract_llm_fail event=reading_llm_error node=reading "
                f"arxiv_id={paper.arxiv_id} detail={e!r}"
            )
            return _reading_block_from_extract(paper, _fallback_reading_extract())

        try:
            if isinstance(raw_out, ReadingExtract):
                ex = ReadingExtract.model_validate(raw_out.model_dump())
            else:
                ex = ReadingExtract.model_validate(raw_out)
        except ValidationError as e:
            pl.warning(
                f"[PaperWF] reading_extract_invalid event=reading_extract_validate_error node=reading "
                f"arxiv_id={paper.arxiv_id} detail={e!r}"
            )
            ex = _fallback_reading_extract()

        return _reading_block_from_extract(paper, ex)

    async def reading_agent_node(state: PaperWorkflowState) -> Dict[str, Any]:
        pl = get_paper_logger(state)
        await event_queue.put(
            {"type": "phase", "data": {"node": "reading", "status": "start", "detail": {}}}
        )
        ws = Path(state.get("workspace_dir") or ".")
        ws.mkdir(parents=True, exist_ok=True)
        md_path = ws / "readings.md"
        papers_raw: List[Dict[str, Any]] = state.get("papers") or []
        if not papers_raw:
            pl.info("[PaperWF] reading_skip event=reading_empty node=reading paper_count=0")
            await event_queue.put(
                {"type": "phase", "data": {"node": "reading", "status": "end", "detail": {"count": 0}}}
            )
            async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
                await f.write("# 阅读摘要\n\n（无检索结果）\n")
            return {
                "readings_md_path": str(md_path),
                "reading_text_for_writing": "",
            }

        max_n = max(1, int(config.paper_arxiv_max_results))
        if len(papers_raw) > max_n:
            pl.warning(
                f"[PaperWF] reading_truncate event=papers_truncated node=reading "
                f"incoming={len(papers_raw)} max_n={max_n}"
            )
            papers_raw = papers_raw[:max_n]

        normalized_rows = [normalize_paper_dict_for_reading(dict(p)) for p in papers_raw]
        normalized_rows.sort(key=lambda d: (d.get("arxiv_id") or "").strip())

        sem = asyncio.Semaphore(max(1, int(config.paper_read_max_concurrent)))

        async def bounded(meta: Dict[str, Any]) -> str:
            async with sem:
                try:
                    paper = PaperMeta.model_validate(meta)
                except ValidationError as e:
                    pl.warning(
                        f"[PaperWF] reading_meta_invalid event=paper_meta_validate_error node=reading detail={e!r}"
                    )
                    aid = str(meta.get("arxiv_id") or "unknown").strip() or "unknown"
                    ttl = str(meta.get("title") or "")
                    return _placeholder_paper_block(aid, ttl, "论文元数据无效，跳过结构化阅读。")

                await event_queue.put(
                    {
                        "type": "reading_progress",
                        "data": {"arxiv_id": paper.arxiv_id, "status": "start"},
                    }
                )
                try:
                    text = await _extract_one(paper, pl)
                finally:
                    await event_queue.put(
                        {
                            "type": "reading_progress",
                            "data": {"arxiv_id": paper.arxiv_id, "status": "end"},
                        }
                    )
                return text

        parts = await asyncio.gather(*[bounded(p) for p in normalized_rows])
        full_md = merge_reading_markdown_blocks(parts)
        async with _file_lock:
            async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
                await f.write(full_md)

        max_chars = int(config.paper_reading_summary_max_chars)
        reading_text = full_md if len(full_md) <= max_chars else full_md[:max_chars] + "\n\n…（已截断，全文见 readings.md）\n"
        pl.info(
            f"[PaperWF] reading_complete event=reading_end node=reading "
            f"path={md_path} md_chars={len(full_md)} paper_count={len(normalized_rows)}"
        )
        await event_queue.put(
            {
                "type": "phase",
                "data": {"node": "reading", "status": "end", "detail": {"count": len(normalized_rows)}},
            }
        )
        return {
            "readings_md_path": str(md_path),
            "reading_text_for_writing": reading_text,
        }

    return reading_agent_node
