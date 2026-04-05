"""
/**
 * @Module: app/services/paper_search_confirm_gate.py
 * @Description: 论文检索前人工确认的可复用闸门：SSE 负载构造、队列等待与结构化查询合并；与 registry、confirm API 配合。
 * @Interface: build_search_confirm_event / build_post_search_confirm_boundary_event / format_search_confirm_assistant_markdown / wait_for_search_confirmation / apply_confirmation_to_structured
 */
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Protocol

from app.agent.paper.schemas import StructuredArxivQuery, normalize_structured_arxiv_query

# @Step: 1 - 与 search 节点原逻辑一致：最多丢弃若干条 run_id 不匹配的误投递
CONFIRM_RUN_ID_MISMATCH_MAX = 10

_CONFIRM_MESSAGE = (
    "请确认或修改检索条件后调用 POST /api/paper/confirm_search（RunId、Approved，可选 "
    "Querys、StartDate、EndDate、TitlePhrase、Author、Categories、SortMode、AdjustmentText）；"
    "载荷需包含 RunId 与 SSE 中 run_id 一致。"
)


class _PaperWorkflowLog(Protocol):
    """与 get_paper_logger 返回对象兼容的最小接口。"""

    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...


def build_search_confirm_event(
    run_id: str,
    structured: StructuredArxivQuery,
    user_request_preview: str,
) -> Dict[str, Any]:
    # @Step: 2 - 供任意调用方推 SSE 或日志，结构与论文流一致
    return {
        "type": "search_confirm",
        "data": {
            "run_id": run_id,
            "structured_query": structured.model_dump(),
            "user_request_preview": user_request_preview[:800],
            "message": _CONFIRM_MESSAGE,
        },
    }


def format_search_confirm_assistant_markdown(
    *,
    run_id: str,
    structured: StructuredArxivQuery,
    user_request_preview: str,
) -> str:
    """
    生成供 SSE type=content 推送的说明正文，便于仅渲染「助手气泡」的前端在阻塞等待 confirm 时仍能展示内容与 run_id。
    """
    # @Agent_Logic: 与 search_confirm 同事务；先 content 再 search_confirm，用户先看到文字再收结构化事件
    preview = (user_request_preview or "").strip()[:400]
    lines = [
        "**以下为拟用于 arXiv 检索的结构化条件：**",
        "",
        f"- **run_id**：`{run_id}`",
    ]
    if preview:
        lines.extend(["", f"- **需求摘要**：{preview}"])
    q = structured.querys or []
    lines.extend(
        [
            "",
            f"- **关键词（querys）**：{', '.join(q) if q else '（无）'}",
            f"- **时间范围**：{structured.start_date or '（不限）'} ~ {structured.end_date or '（不限）'}",
            f"- **标题短语（title_phrase）**：{structured.title_phrase or '（无）'}",
            f"- **作者（author）**：{structured.author or '（无）'}",
            f"- **分类（categories）**：{', '.join(structured.categories) if structured.categories else '（无）'}",
            f"- **排序（sort_mode）**：{structured.sort_mode}",
        ]
    )
    return "\n".join(lines)


POST_SEARCH_CONFIRM_BOUNDARY_REASON = "post_search_confirm"


def build_post_search_confirm_boundary_event(run_id: str) -> Dict[str, Any]:
    """
    用户已通过 confirm_search 后、即将执行 arXiv 检索前推送，供前端将助手消息分段（新气泡承接后续 phase/content）。
    """
    return {
        "type": "assistant_message_boundary",
        "data": {
            "run_id": run_id,
            "reason": POST_SEARCH_CONFIRM_BOUNDARY_REASON,
            "label": "检索已确认，以下为执行与报告输出",
        },
    }


async def wait_for_search_confirmation(
    *,
    run_id: str,
    confirm_queue: asyncio.Queue,
    timeout_sec: float,
    paper_log: _PaperWorkflowLog,
) -> Dict[str, Any]:
    """
    从注册表注入的队列读取一条与 run_id 匹配的确认载荷。
    超时、多次 run_id 不匹配、或 approved=false 时抛出 RuntimeError（文案与原 search 节点一致）。
    """
    # @Agent_Logic: 与 HTTP submit_search_confirmation 投递格式一致；拒绝时带 reason
    # @Security: 校验 run_id 防止跨 run 误确认

    async def _recv_matching_confirm() -> Dict[str, Any]:
        for mismatch_idx in range(CONFIRM_RUN_ID_MISMATCH_MAX):
            msg = await confirm_queue.get()
            rid = str(msg.get("run_id", "")).strip()
            if rid == run_id:
                return msg
            paper_log.warning(
                f"[PaperWF] search_confirm_mismatch event=confirm_run_id_mismatch node=search "
                f"expect_run_id={run_id!r} got_run_id={rid!r} "
                f"attempt={mismatch_idx + 1}/{CONFIRM_RUN_ID_MISMATCH_MAX}"
            )
        raise RuntimeError(
            "search_confirm_mismatch: 多次收到与当前运行不一致的确认，请重试"
        )

    try:
        if timeout_sec > 0:
            msg = await asyncio.wait_for(
                _recv_matching_confirm(),
                timeout=timeout_sec,
            )
        else:
            msg = await _recv_matching_confirm()
    except asyncio.TimeoutError:
        paper_log.error("[PaperWF] search_confirm_timeout event=confirm_timeout node=search")
        raise RuntimeError(
            "search_confirm_timeout: 等待人工确认超时，请重开工作流或调大 PAPER_SEARCH_CONFIRM_TIMEOUT_SEC"
        ) from None

    if not msg.get("approved", False):
        reason = (msg.get("reason") or "用户未批准检索").strip()
        paper_log.info(
            f"[PaperWF] search_rejected event=confirm_rejected node=search reason_preview={reason[:120]!r}"
        )
        raise RuntimeError(f"search_rejected: {reason}")

    return msg


def apply_confirmation_to_structured(
    structured: StructuredArxivQuery,
    msg: Dict[str, Any],
) -> StructuredArxivQuery:
    """
    将用户确认的覆盖项合并进结构化查询并 normalize。
    调用方须保证 msg 已通过 wait_for_search_confirmation（即已批准）。
    非空显式字段覆盖当前值；adjustment_text 仅由 search 节点在调用本函数前用于 NL 修订，此处忽略。
    """
    # @Step: 3 - 与 confirm API 载荷字段对齐；显式覆盖优先于此前 NL 修订结果
    q_override = msg.get("querys")
    out = structured
    if isinstance(q_override, list) and len(q_override) > 0:
        cleaned = [str(x).strip() for x in q_override if str(x).strip()]
        if cleaned:
            out = StructuredArxivQuery(
                querys=cleaned,
                start_date=out.start_date or "",
                end_date=out.end_date or "",
                title_phrase=out.title_phrase or "",
                author=out.author or "",
                sort_mode=out.sort_mode,
                categories=list(out.categories or []),
            )
    sd = msg.get("start_date")
    ed = msg.get("end_date")
    if isinstance(sd, str) and sd.strip():
        out = out.model_copy(update={"start_date": sd.strip()})
    if isinstance(ed, str) and ed.strip():
        out = out.model_copy(update={"end_date": ed.strip()})

    tp = msg.get("title_phrase")
    if isinstance(tp, str) and tp.strip():
        out = out.model_copy(update={"title_phrase": tp.strip()})

    au = msg.get("author")
    if isinstance(au, str) and au.strip():
        out = out.model_copy(update={"author": au.strip()})

    cats = msg.get("categories")
    if isinstance(cats, list) and len(cats) > 0:
        cleaned_cats = [str(c).strip() for c in cats if str(c).strip()]
        if cleaned_cats:
            out = out.model_copy(update={"categories": cleaned_cats})

    sm = msg.get("sort_mode")
    if sm in ("relevance", "submitted_date"):
        out = out.model_copy(update={"sort_mode": sm})

    return normalize_structured_arxiv_query(out)
