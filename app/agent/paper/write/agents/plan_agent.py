"""
/**
 * @Module: app/agent/paper/write/agents/plan_agent.py
 * @Description: 「大纲规划」独立智能体：含首版/Replan 两套系统提示词；可选知识库检索 + 结构化 OutlineResponse。
 * @Interface: run_writing_plan
 *
 * 对应写作子图节点：writePlan（入口见 nodes/writing_plan_node.py）。
 */
"""

from __future__ import annotations

import asyncio
import json
from textwrap import dedent
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.schemas import OutlineResponse, SectionTask
from app.agent.paper.state import PaperWorkflowState
from app.config import config
from app.tools.knowledge_tool import retrieve_knowledge
from app.utils.paper_workflow_logging import get_paper_logger

# @Agent_Logic: 本文件独立维护 Planner 的 system/human 模板，与子图其他智能体分离。

WRITE_PLAN_SYSTEM_PROMPT_FIRST = dedent(
    """
    你是调研报告主编。根据用户需求、论文阅读摘要与知识库摘录，设计 Markdown 报告大纲。
    输出 4～8 个 section，每个含 section_id（英文蛇形，唯一）、title（中文）、
    objectives（本章节写作目标）、keywords_for_retrieval（供知识库检索的短查询，空格分隔关键词）。
    章节应覆盖背景、方法对比、趋势、挑战、结论等（按需取舍）。
    """
).strip()

WRITE_PLAN_HUMAN_PROMPT_FIRST = dedent(
    """
    【用户需求】
    {user_request}

    【阅读摘要】
    {reading}

    【知识库摘录】
    {knowledge}
    """
).strip()

WRITE_PLAN_SYSTEM_PROMPT_REPLAN = dedent(
    """
    你是调研报告主编。当前为「改纲」：在保留未点名章节的前提下，按审稿意见调整大纲。
    规则：
    - 对于「不需改动的 section_id」（不在 affected 列表中），必须在输出中**原样复制**其 title、objectives、keywords_for_retrieval（与旧大纲一致）。
    - 对于 affected 中的章节，可修改标题/目标/检索词，也可调整顺序；可新增 section（新 section_id 蛇形英文唯一）。
    - 输出完整章节列表（4～8 节为宜），结构为 OutlineResponse。
    """
).strip()

WRITE_PLAN_HUMAN_PROMPT_REPLAN = dedent(
    """
    【用户需求】
    {user_request}

    【阅读摘要】
    {reading}

    【知识库摘录】
    {knowledge}

    【审稿改纲意见】
    {hint}

    【需重点调整的 section_id 列表】
    {affected}

    【当前大纲 JSON】
    {old_outline_json}
    """
).strip()


def _merge_outline_on_replan(
    old_rows: List[Dict[str, Any]],
    proposed: OutlineResponse,
    affected_ids: List[str],
) -> List[Dict[str, Any]]:
    affected_set = {str(x).strip() for x in (affected_ids or []) if str(x).strip()}
    old_by_id = {str(r.get("section_id") or ""): dict(r) for r in old_rows if r.get("section_id")}
    merged: List[Dict[str, Any]] = []
    for s in proposed.sections:
        sid = s.section_id
        if sid in old_by_id and sid not in affected_set:
            merged.append(old_by_id[sid])
        else:
            merged.append(s.model_dump())
    merged_ids = {str(r.get("section_id") or "") for r in merged}
    for sid, user_row in old_by_id.items():
        if sid and sid not in merged_ids:
            merged.append(user_row)
    return merged


def _compute_dirty_section_ids(
    old_ids: set[str],
    new_rows: List[Dict[str, Any]],
    affected_ids: List[str],
    is_replan: bool,
) -> List[str]:
    new_ids = {str(r.get("section_id") or "") for r in new_rows if r.get("section_id")}
    if not is_replan:
        return sorted(new_ids)
    aff = {str(x).strip() for x in (affected_ids or []) if str(x).strip()}
    if not aff:
        return sorted(new_ids)
    dirty = set(aff) | (new_ids - old_ids)
    return sorted(dirty)


def _build_planning_knowledge_query(
    *,
    user_request: str,
    reading_excerpt: str,
    old_outline: List[Dict[str, Any]],
    is_replan: bool,
    replan_hint: str,
    pl,
) -> str:
    """组装 Planner 阶段单次 retrieve_knowledge 的 query：用户意图 + 阅读片段 + Replan 时大纲检索词与改纲提示。"""
    qmax = max(300, int(config.paper_planning_knowledge_query_max_chars))
    parts: List[str] = []
    ur = (user_request or "").strip()[:400]
    if ur:
        parts.append(ur)

    read_snip = (reading_excerpt or "").strip()[:350]
    if read_snip and not read_snip.startswith("（无阅读摘要"):
        parts.append(read_snip)

    if is_replan and old_outline:
        seen: Dict[str, None] = {}
        merged_kw_parts: List[str] = []
        for row in old_outline:
            k = str(row.get("keywords_for_retrieval") or "").strip()
            if k and k not in seen:
                seen[k] = None
                merged_kw_parts.append(k)
        merged_kw = " ".join(merged_kw_parts)
        if merged_kw:
            parts.append(merged_kw[:400])
        rh = (replan_hint or "").strip()[:250]
        if rh:
            parts.append(rh)

    raw = " ".join(parts).strip()
    if not raw:
        raw = "学术调研 综述"
    if len(raw) > qmax:
        pl.warning(
            f"[PaperWF] plan_rag_query_truncated event=planning_query_truncated node=writePlan "
            f"len={len(raw)} max={qmax}"
        )
        raw = raw[:qmax]
    pl.info(
        f"[PaperWF] plan_rag_query event=planning_rag_query_built node=writePlan "
        f"len={len(raw)} preview={raw[:80]!r}..."
    )
    return raw


async def run_writing_plan(state: PaperWorkflowState) -> Dict[str, Any]:
    pl = get_paper_logger(state)
    user_request = (state.get("user_request") or "").strip()
    reading = state.get("reading_text_for_writing") or "（无阅读摘要）"
    read_max = max(500, int(config.paper_planning_reading_max_chars))
    know_max = max(500, int(config.paper_planning_knowledge_max_chars))
    reading_excerpt = reading[:read_max]

    replan_hint = (state.get("writing_replan_hint") or "").strip()
    affected_ids: List[str] = list(state.get("writing_replan_affected_ids") or [])
    old_outline: List[Dict[str, Any]] = list(state.get("outline_sections") or [])
    is_replan = bool(replan_hint or affected_ids)

    if config.paper_writing_rag_enabled:
        query = _build_planning_knowledge_query(
            user_request=user_request,
            reading_excerpt=reading_excerpt,
            old_outline=old_outline,
            is_replan=is_replan,
            replan_hint=replan_hint,
            pl=pl,
        )
        try:
            content, _docs = await asyncio.to_thread(
                retrieve_knowledge.invoke,
                {"query": query},
            )
            knowledge_excerpt = (content or "")[:know_max]
            pl.info(
                f"[PaperWF] plan_rag_ok event=planning_retrieve_ok node=writePlan "
                f"knowledge_chars={len(knowledge_excerpt)}"
            )
        except Exception as e:
            pl.warning(
                f"[PaperWF] plan_rag_fail event=planning_retrieve_error node=writePlan detail={e!r}"
            )
            knowledge_excerpt = f"（知识库检索失败: {e}）"
    else:
        pl.info("[PaperWF] plan_rag_skipped event=planning_rag_disabled node=writePlan")
        knowledge_excerpt = "（未启用写作阶段知识库检索；大纲仅依据用户需求与阅读摘要。）"

    llm = get_paper_chat_model(temperature=0.3, streaming=False)
    structured = llm.with_structured_output(OutlineResponse)

    if is_replan:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", WRITE_PLAN_SYSTEM_PROMPT_REPLAN),
                ("human", WRITE_PLAN_HUMAN_PROMPT_REPLAN),
            ]
        )
        chain = prompt | structured
        try:
            outline_raw = await chain.ainvoke(
                {
                    "user_request": user_request,
                    "reading": reading_excerpt,
                    "knowledge": knowledge_excerpt,
                    "hint": replan_hint or "（无具体说明，请适度优化结构）",
                    "affected": json.dumps(affected_ids, ensure_ascii=False),
                    "old_outline_json": json.dumps(old_outline, ensure_ascii=False)[:12000],
                }
            )
            outline = (
                outline_raw
                if isinstance(outline_raw, OutlineResponse)
                else OutlineResponse.model_validate(outline_raw)
            )
        except Exception as e:
            pl.error(f"[PaperWF] plan_replan_llm_fail event=plan_replan_error node=writePlan detail={e!r}")
            try:
                outline = OutlineResponse(
                    sections=[SectionTask.model_validate(x) for x in old_outline]
                )
            except Exception:
                outline = OutlineResponse(sections=[])

        merged_rows = _merge_outline_on_replan(old_outline, outline, affected_ids)
        old_ids = {str(r.get("section_id") or "") for r in old_outline if r.get("section_id")}
        dirty = _compute_dirty_section_ids(old_ids, merged_rows, affected_ids, True)
        sections_dump = merged_rows
    else:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", WRITE_PLAN_SYSTEM_PROMPT_FIRST),
                ("human", WRITE_PLAN_HUMAN_PROMPT_FIRST),
            ]
        )
        chain = prompt | structured
        try:
            outline_raw = await chain.ainvoke(
                {
                    "user_request": user_request,
                    "reading": reading_excerpt,
                    "knowledge": knowledge_excerpt,
                }
            )
            outline = (
                outline_raw
                if isinstance(outline_raw, OutlineResponse)
                else OutlineResponse.model_validate(outline_raw)
            )
        except Exception as e:
            pl.error(f"[PaperWF] plan_first_llm_fail event=plan_outline_error node=writePlan detail={e!r}")
            outline = OutlineResponse(
                sections=[
                    SectionTask(
                        section_id="overview",
                        title="概述",
                        objectives="概括主题与论文脉络",
                        keywords_for_retrieval=user_request[:200] or "调研 综述",
                    ),
                    SectionTask(
                        section_id="analysis",
                        title="分析与讨论",
                        objectives="结合摘要进行分析",
                        keywords_for_retrieval="",
                    ),
                    SectionTask(
                        section_id="conclusion",
                        title="结论与展望",
                        objectives="总结与后续工作",
                        keywords_for_retrieval="",
                    ),
                ]
            )
        sections_dump = [s.model_dump() for s in outline.sections]
        dirty = _compute_dirty_section_ids(set(), sections_dump, [], False)

    pl.info(
        f"[PaperWF] plan_done event=write_plan_end node=writePlan "
        f"is_replan={is_replan} section_count={len(sections_dump)} "
        f"dirty_count={len(dirty)}"
    )

    return {
        "outline_sections": sections_dump,
        "writing_dirty_section_ids": dirty,
        "planning_knowledge_excerpt": knowledge_excerpt[:2000],
        "writing_replan_hint": "",
        "writing_replan_affected_ids": [],
    }
