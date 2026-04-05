"""
/**
 * @Module: app/agent/paper/schemas.py
 * @Description: 论文工作流结构化输出（arXiv 查询、阅读抽取、大纲、审查）。
 * @Interface: StructuredArxivQuery / normalize_structured_arxiv_query / PaperMeta / normalize_paper_dict_for_reading / paper_meta_to_search_result_record / ReadingExtract / OutlineResponse / ReviewDecision / WritingGlobalReview
 */
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any, List, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

# arXiv 关键词规范化上限（与 search 节点 prompt 中 2～5 条对齐，允许最多 5 条）
MAX_ARXIV_QUERYS = 5
MAX_ARXIV_QUERY_TERM_LEN = 120
MAX_ARXIV_TITLE_PHRASE_LEN = 200
MAX_ARXIV_AUTHOR_LEN = 120
MAX_ARXIV_CATEGORIES = 5
MAX_ARXIV_CATEGORY_TOKEN_LEN = 32

# 阅读节点入参：与工具 JSON 对齐（作者/分类条数上限）
MAX_READING_SOURCE_AUTHORS = 20
MAX_READING_SOURCE_CATEGORIES = 20
# 单字段 LLM 抽取上限（与 reading 节点 prompt 简练段落一致）
MAX_READING_EXTRACT_FIELD_LEN = 4000

ArxivSortMode = Literal["relevance", "submitted_date"]


class StructuredArxivQuery(BaseModel):
    """LLM 将自然语言转为 arXiv 检索条件。"""

    querys: List[str] = Field(
        default_factory=list,
        description="检索关键词或短语列表，将映射为 arXiv all: 字段 OR 组合；优先英文",
    )
    start_date: str = Field(
        default="",
        description="起始日期 YYYY-MM-DD，空表示不限制下界",
    )
    end_date: str = Field(
        default="",
        description="结束日期 YYYY-MM-DD，空表示不限制上界",
    )
    title_phrase: str = Field(
        default="",
        description="用户明确按标题查找时的短语，映射为 arXiv ti:；优先英文",
    )
    author: str = Field(
        default="",
        description="作者名，映射为 arXiv au:；可含空格",
    )
    sort_mode: ArxivSortMode = Field(
        default="relevance",
        description="relevance=相关度；submitted_date=按提交时间降序（适合「最新」「最近」）",
    )
    categories: List[str] = Field(
        default_factory=list,
        description="arXiv 分类码 OR 组合，如 cs.LG、cs.AI；不确定则留空",
    )


def normalize_structured_arxiv_query(q: StructuredArxivQuery) -> StructuredArxivQuery:
    """去空、去重、条数与单条长度上限，避免 OR 查询过长或发散。"""
    seen: set[str] = set()
    out: List[str] = []
    for raw in q.querys or []:
        s = (raw or "").strip()
        if not s:
            continue
        if len(s) > MAX_ARXIV_QUERY_TERM_LEN:
            logger.warning(
                f"[WARN][StructuredArxivQuery]: 单条关键词截断 len={len(s)} -> {MAX_ARXIV_QUERY_TERM_LEN}"
            )
            s = s[:MAX_ARXIV_QUERY_TERM_LEN]
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= MAX_ARXIV_QUERYS:
            break

    tp = (q.title_phrase or "").strip()
    if len(tp) > MAX_ARXIV_TITLE_PHRASE_LEN:
        logger.warning("[WARN][StructuredArxivQuery]: title_phrase 截断")
        tp = tp[:MAX_ARXIV_TITLE_PHRASE_LEN]

    au = (q.author or "").strip()
    if len(au) > MAX_ARXIV_AUTHOR_LEN:
        logger.warning("[WARN][StructuredArxivQuery]: author 截断")
        au = au[:MAX_ARXIV_AUTHOR_LEN]

    cat_seen: set[str] = set()
    cats_out: List[str] = []
    for raw in q.categories or []:
        c = (raw or "").strip().replace('"', "").replace(" ", "")
        if not c:
            continue
        if len(c) > MAX_ARXIV_CATEGORY_TOKEN_LEN:
            c = c[:MAX_ARXIV_CATEGORY_TOKEN_LEN]
        ck = c.lower()
        if ck in cat_seen:
            continue
        cat_seen.add(ck)
        cats_out.append(c)
        if len(cats_out) >= MAX_ARXIV_CATEGORIES:
            break

    sm: ArxivSortMode = q.sort_mode if q.sort_mode in ("relevance", "submitted_date") else "relevance"

    return q.model_copy(
        update={
            "querys": out,
            "title_phrase": tp,
            "author": au,
            "start_date": (q.start_date or "").strip(),
            "end_date": (q.end_date or "").strip(),
            "sort_mode": sm,
            "categories": cats_out,
        }
    )


class PaperMeta(BaseModel):
    """单篇论文元数据（来自 arXiv Atom）。"""

    arxiv_id: str
    # 短 id，含版本后缀（如 2411.11607v2）；与 arxiv.Result.get_short_id() 一致
    arxiv_short_id: str = ""
    title: str
    authors: List[str] = Field(default_factory=list)
    published: str = ""
    # 从 result.published 提取的公历年；旧数据或解析失败时可为 None
    published_year: int | None = None
    summary: str = ""
    pdf_url: str = ""
    abs_url: str = ""
    # arXiv 主分类与全部分类（如 cs.CR）
    primary_category: str = ""
    categories: List[str] = Field(default_factory=list)





def _strip_arxiv_version_suffix(arxiv_id: str) -> str:
    s = (arxiv_id or "").strip()
    if not s:
        return s
    return re.sub(r"v\d+$", "", s, flags=re.IGNORECASE)


def normalize_paper_dict_for_reading(raw: dict[str, Any]) -> dict[str, Any]:
    """工具 JSON（summary_excerpt/category）与 PaperMeta.model_dump 对齐，供 reading 节点校验前调用。"""
    d = dict(raw)
    aid = _strip_arxiv_version_suffix(str(d.get("arxiv_id") or ""))
    if aid:
        d["arxiv_id"] = aid
    summ = (d.get("summary") or "").strip()
    if not summ:
        excerpt = (d.get("summary_excerpt") or "").strip()
        if excerpt.endswith("…") or excerpt.endswith("..."):
            excerpt = excerpt[:-1].rstrip()
        d["summary"] = excerpt
    pc = (d.get("primary_category") or "").strip()
    if not pc:
        cat = (d.get("category") or "").strip()
        if cat:
            d["primary_category"] = cat
    authors = d.get("authors")
    if isinstance(authors, list):
        d["authors"] = [str(a).strip() for a in authors if str(a).strip()][:MAX_READING_SOURCE_AUTHORS]
    else:
        d["authors"] = []
    cats = d.get("categories")
    if isinstance(cats, list):
        d["categories"] = [str(c).strip() for c in cats if str(c).strip()][:MAX_READING_SOURCE_CATEGORIES]
    else:
        d["categories"] = []
    sid = (d.get("arxiv_short_id") or "").strip()
    if not sid and aid:
        d["arxiv_short_id"] = aid
    return d


def paper_meta_to_search_result_record(meta: PaperMeta) -> dict[str, Any]:
    """
    对外展示用扁平结构：paper_id 为短 id，published 为整数年份，url 为摘要页；category 为主类，categories 为全部分类。
    """
    year = meta.published_year
    if year is None and (meta.published or "").strip():
        try:
            s = meta.published.strip().replace("Z", "+00:00")
            year = datetime.fromisoformat(s).year
        except (ValueError, TypeError):
            year = None
    cats = list(meta.categories)
    primary = (meta.primary_category or "").strip()
    if not primary and cats:
        primary = cats[0]
    return {
        "paper_id": (meta.arxiv_short_id or meta.arxiv_id).strip(),
        "title": meta.title,
        "authors": list(meta.authors),
        "summary": meta.summary,
        "published": year,
        "category": primary,
        "categories": cats,
        "url": (meta.abs_url or "").strip(),
    }


class ReadingExtract(BaseModel):
    """单篇阅读结构化摘要。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    core_problem: str = Field(default="", max_length=MAX_READING_EXTRACT_FIELD_LEN)
    key_methods: str = Field(default="", max_length=MAX_READING_EXTRACT_FIELD_LEN)
    innovation: str = Field(default="", max_length=MAX_READING_EXTRACT_FIELD_LEN)
    limitations: str = Field(default="", max_length=MAX_READING_EXTRACT_FIELD_LEN)
    contributions: str = Field(default="", max_length=MAX_READING_EXTRACT_FIELD_LEN)



class SectionTask(BaseModel):
    """写作子任务。"""

    section_id: str
    title: str
    objectives: str = ""
    keywords_for_retrieval: str = ""


class OutlineResponse(BaseModel):
    """写作大纲与子任务列表。"""

    sections: List[SectionTask] = Field(default_factory=list)


class ReviewDecision(BaseModel):
    """章节质量审查。"""

    decision: Literal["APPROVE", "REVISE"] = "REVISE"
    comment: str = ""


class WritingGlobalReview(BaseModel):
    """全局写作评审：决定继续终稿、局部改稿或改纲（Replan）。"""

    decision: Literal["OK", "REVISE", "REPLAN"] = "REVISE"
    comment: str = ""
    replan_hint: str = ""
    replan_affected_section_ids: List[str] = Field(default_factory=list)
    revise_section_ids: List[str] = Field(default_factory=list)
