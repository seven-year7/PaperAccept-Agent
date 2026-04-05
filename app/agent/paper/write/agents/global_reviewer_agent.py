"""
/**
 * @Module: app/agent/paper/write/agents/global_reviewer_agent.py
 * @Description: 「全局总编辑」独立智能体：系统提示词定义 OK/REVISE/REPLAN；含路由状态与调用次数上限。
 * @Interface: run_global_writing_review
 *
 * 对应子图节点：writeAudit（入口见 nodes/writing_reviewer_node.py，仅转调）。
 */
"""

from __future__ import annotations

import asyncio
import json
from textwrap import dedent
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.schemas import WritingGlobalReview
from app.agent.paper.state import PaperWorkflowState
from app.config import config
from app.utils.paper_workflow_logging import get_paper_logger

# @Agent_Logic: 全局把关协议仅在本文件维护，与单章 Writer/SectionReviewer 分离。

GLOBAL_EDITOR_SYSTEM_PROMPT = dedent(
    """
    你是总编辑，对整份报告草稿做全局把关。
    各章正文在上下文中仅为长度预算内的摘录，未见部分仍可能存在有效论述；勿因摘录较短就断定章节空洞，必要时标 REVISE 并说明需作者通读全文核实。
    - OK：结构合理、与用户需求一致、各章基本成稿，可进入终稿润色。
    - REVISE：大纲可保留，但需改某些章节正文；在 revise_section_ids 列出要重写的 section_id（蛇形），comment 写清修改要求。若不确定则列出所有章节 id。
    - REPLAN：大纲或章节设置有问题，需主编重新规划；写 replan_hint，并在 replan_affected_section_ids 列出需调整或重写的 section_id（至少一个，除非需全新大纲则列出全部现有 id）。
    """
).strip()

GLOBAL_EDITOR_HUMAN_PROMPT = dedent(
    """
    【用户需求】
    {user_request}

    【大纲 JSON】
    {outline}

    【各章正文摘录】
    以下每节均在总长度预算内均匀截取（长章可能含「中略」），未展示段落不代表不存在。
    {bundle}
    """
).strip()


def _excerpt_body_for_global_review(body: str, quota: int) -> str:
    if quota <= 0:
        return ""
    if len(body) <= quota:
        return body
    if quota < 160:
        return body[:quota]
    head = (quota * 2) // 3
    tail = quota - head - len("\n…[中略]…\n")
    if tail < 30:
        return body[:quota]
    return body[:head] + "\n…[中略]…\n" + body[-tail:]


def _build_review_bundle(state: PaperWorkflowState) -> str:
    pl = get_paper_logger(state)
    outline: List[Dict[str, Any]] = list(state.get("outline_sections") or [])
    sections: Dict[str, str] = dict(state.get("sections") or {})
    budget = max(2000, int(config.paper_global_review_max_chars))
    n = len(outline)
    if n == 0:
        return ""

    min_desired = max(0, int(config.paper_global_review_min_chars_per_section))

    header_lines: List[str] = []
    for row in outline:
        sid = str(row.get("section_id") or "")
        title = str(row.get("title") or sid)
        if len(title) > 80:
            title = title[:77] + "..."
        header_lines.append(f"### {sid} — {title}\n")

    headers_total = sum(len(h) for h in header_lines)
    avail = max(0, budget - headers_total)
    body_per = avail // n

    if min_desired > 0 and body_per < min_desired:
        pl.info(
            f"[PaperWF] audit_bundle_quota event=global_review_body_quota node=writeAudit "
            f"body_per={body_per} min_desired={min_desired}"
        )

    parts: List[str] = []
    for header, row in zip(header_lines, outline):
        sid = str(row.get("section_id") or "")
        body = sections.get(sid, "（本节尚无正文）")
        chunk = _excerpt_body_for_global_review(body, body_per)
        parts.append(f"{header}{chunk}\n")

    out = "\n".join(parts)
    if len(out) > budget:
        pl.warning(
            f"[PaperWF] audit_bundle_truncated event=global_review_bundle_truncated node=writeAudit "
            f"len={len(out)} budget={budget}"
        )
        out = out[:budget]
    pl.info(
        f"[PaperWF] audit_bundle_built event=global_review_bundle_ready node=writeAudit "
        f"sections={n} budget={budget} body_per_section={body_per} out_len={len(out)}"
    )
    return out


def _all_section_ids(state: PaperWorkflowState) -> List[str]:
    return [
        str(r.get("section_id") or "")
        for r in (state.get("outline_sections") or [])
        if r.get("section_id")
    ]


async def _run_global_writing_review_llm(state: PaperWorkflowState) -> WritingGlobalReview:
    pl = get_paper_logger(state)
    user_request = (state.get("user_request") or "").strip()
    bundle = _build_review_bundle(state)
    outline_json = json.dumps(state.get("outline_sections") or [], ensure_ascii=False)[:6000]

    llm = get_paper_chat_model(temperature=0.0, streaming=False).with_structured_output(
        WritingGlobalReview
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", GLOBAL_EDITOR_SYSTEM_PROMPT),
            ("human", GLOBAL_EDITOR_HUMAN_PROMPT),
        ]
    )
    chain = prompt | llm
    try:
        return await chain.ainvoke(
            {
                "user_request": user_request,
                "outline": outline_json,
                "bundle": bundle,
            }
        )
    except Exception as e:
        pl.warning(
            f"[PaperWF] audit_llm_fail event=global_review_llm_error node=writeAudit detail={e!r} "
            f"fallback_decision=REVISE"
        )
        return WritingGlobalReview(
            decision="REVISE",
            comment=f"全局审稿调用失败，请收紧各章。detail={e}",
            revise_section_ids=_all_section_ids(state),
        )


async def run_global_writing_review(
    state: PaperWorkflowState,
    event_queue: asyncio.Queue,
    *,
    phase_node: str,
    route_to_execute: str,
    route_to_plan: str,
    route_to_done: str,
) -> Dict[str, Any]:
    pl = get_paper_logger(state)
    await event_queue.put(
        {"type": "phase", "data": {"node": phase_node, "status": "start", "detail": {}}}
    )
    max_inv = max(1, int(config.paper_writing_max_reviewer_invocations))
    prev = int(state.get("writing_reviewer_invocations") or 0)

    if prev >= max_inv:
        pl.warning(
            f"[PaperWF] audit_cap_force_end event=global_review_cap node=writeAudit "
            f"max_inv={max_inv} action=route_done"
        )
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": phase_node,
                    "status": "end",
                    "detail": {"decision": "OK", "forced": True},
                },
            }
        )
        return {"writing_route_next": route_to_done}

    result = await _run_global_writing_review_llm(state)
    new_inv = prev + 1

    if new_inv >= max_inv and result.decision != "OK":
        pl.warning(
            f"[PaperWF] audit_force_ok event=global_review_last_invocation node=writeAudit "
            f"invocation={new_inv} max_inv={max_inv} prior_decision={result.decision}"
        )
        result = WritingGlobalReview(
            decision="OK",
            comment="已达全局审稿次数上限，采纳当前稿。",
        )

    all_ids = _all_section_ids(state)
    detail: Dict[str, Any] = {"decision": result.decision, "invocation": new_inv}

    if result.decision == "OK":
        pl.info(
            f"[PaperWF] audit_decision event=write_audit_end node=writeAudit "
            f"decision=OK invocation={new_inv} route=done"
        )
        await event_queue.put(
            {"type": "phase", "data": {"node": phase_node, "status": "end", "detail": detail}}
        )
        return {
            "writing_reviewer_invocations": new_inv,
            "writing_route_next": route_to_done,
            "writing_dirty_section_ids": [],
        }

    if result.decision == "REVISE":
        dirty = [x for x in (result.revise_section_ids or []) if x.strip()]
        if not dirty:
            dirty = list(all_ids)
        detail["revise_sections"] = len(dirty)
        pl.info(
            f"[PaperWF] audit_decision event=write_audit_end node=writeAudit "
            f"decision=REVISE invocation={new_inv} dirty_count={len(dirty)} route=writeExecute"
        )
        await event_queue.put(
            {"type": "phase", "data": {"node": phase_node, "status": "end", "detail": detail}}
        )
        return {
            "writing_reviewer_invocations": new_inv,
            "writing_route_next": route_to_execute,
            "writing_last_review_comment": result.comment or "请按审稿意见修订各章。",
            "writing_dirty_section_ids": dirty,
        }

    affected = [x for x in (result.replan_affected_section_ids or []) if str(x).strip()]
    if not affected:
        affected = list(all_ids)
    detail["replan_affected"] = len(affected)
    pl.info(
        f"[PaperWF] audit_decision event=write_audit_end node=writeAudit "
        f"decision=REPLAN invocation={new_inv} affected_count={len(affected)} route=writePlan"
    )
    await event_queue.put(
        {"type": "phase", "data": {"node": phase_node, "status": "end", "detail": detail}}
    )
    return {
        "writing_reviewer_invocations": new_inv,
        "writing_route_next": route_to_plan,
        "writing_replan_hint": result.replan_hint or result.comment or "请调整大纲结构。",
        "writing_replan_affected_ids": affected,
    }
