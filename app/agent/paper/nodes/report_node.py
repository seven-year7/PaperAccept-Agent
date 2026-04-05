"""
/**
 * @Module: app/agent/paper/nodes/report_node.py
 * @Description: 报告节点：按大纲合并章节正文 → 参考「组装式终稿」提示词流式润色 → SSE content/phase → 落盘 report.md。
 * @Interface: make_report_agent_node
 *
 * 融合说明：对齐外部队列式 report 节点的阶段语义（initializing / streaming / completed）与 Markdown 组装要求，
 * 底层仍使用 LangChain ChatOpenAI.astream + 本项目 event_queue 协议（type=phase|content）。
 */
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent
from typing import Any, Awaitable, Callable, Dict, List

from langchain_core.messages import HumanMessage

from app.agent.paper.llm_utils import get_paper_chat_model
from app.agent.paper.state import PaperWorkflowState
from app.config import config
from app.utils.paper_workflow_logging import get_paper_logger
from app.utils.tenant_id import normalize_tenant_id

# @Agent_Logic: 与用户提供的 report 节点提示一致，并追加「用户需求」上下文，便于终稿对齐调研目标。


def _assemble_sections_markdown(
    outline: List[Dict[str, Any]],
    sections: Dict[str, str],
) -> str:
    """按大纲顺序拼接章节正文（等价于参考代码中的 join 语义）。"""
    if not outline:
        return "无章节内容提供"
    blocks: List[str] = []
    for sec in outline:
        sid = str(sec.get("section_id") or "")
        title = str(sec.get("title") or sid)
        body = (sections or {}).get(sid, "（本节未生成）")
        blocks.append(f"## {title}\n\n{body}\n")
    return "\n".join(blocks)


def _build_report_polish_prompt(*, user_request: str, sections_text: str) -> str:
    return dedent(
        f"""
        请将以下提供的章节内容组装成一份完整的调研报告，并以 Markdown 格式输出。

        【用户需求】
        {user_request.strip() or "（未提供）"}

        【章节内容开始】
        {sections_text}
        【章节内容结束】

        【输出要求】
        1. 使用 Markdown 格式进行排版（标题、列表、加粗等）
        2. 自动补充必要的过渡语句使报告连贯
        3. 保持专业学术风格
        4. 直接输出完整报告，无需解释过程

        【额外说明】
        请确保章节逻辑顺序合理，如有需要可调整章节排列；不得编造未出现在章节内容中的引用或来源。
        """
    ).strip()


def make_report_agent_node(
    event_queue: asyncio.Queue,
) -> Callable[[PaperWorkflowState], Awaitable[Dict[str, Any]]]:
    async def report_agent_node(state: PaperWorkflowState) -> Dict[str, Any]:
        pl = get_paper_logger(state)
        # @Step: 1 - 阶段：初始化（对齐参考 BackToFrontData initializing）
        pl.info(
            f"[PaperWF] report_start event=report_phase node=report "
            f"outline_sections={len(state.get('outline_sections') or [])} "
            f"sections_keys={len(state.get('sections') or {})}"
        )
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": "report",
                    "status": "start",
                    "detail": {"stage": "initializing"},
                },
            }
        )
        ws = Path(state.get("workspace_dir") or ".")
        outline: List[Dict[str, Any]] = list(state.get("outline_sections") or [])
        sections: Dict[str, str] = dict(state.get("sections") or {})
        user_request = state.get("user_request") or ""

        sections_text = _assemble_sections_markdown(outline, sections)
        polish_instructions = _build_report_polish_prompt(
            user_request=user_request,
            sections_text=sections_text,
        )

        stream_llm = get_paper_chat_model(temperature=0.3, streaming=True)
        stream_llm = stream_llm.bind(max_tokens=int(config.paper_report_stream_max_tokens))
        polish_messages = [HumanMessage(content=polish_instructions)]

        # @Step: 2 - 流式润色（对齐参考 streaming；chunk 映射为 content）
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": "report",
                    "status": "running",
                    "detail": {"stage": "streaming"},
                },
            }
        )

        assembled: list[str] = []
        stream_fallback = False
        raw_fallback = (
            f"# 调研报告\n\n> 用户需求：{user_request}\n\n{sections_text}"
            if sections_text != "无章节内容提供"
            else "# 调研报告\n\n（无章节内容提供）"
        )

        try:
            async for chunk in stream_llm.astream(polish_messages):
                piece = getattr(chunk, "content", None) or ""
                if isinstance(piece, list):
                    # 少数多模态块：拼文本
                    piece = "".join(
                        str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in piece
                    )
                if piece:
                    assembled.append(str(piece))
                    await event_queue.put({"type": "content", "data": str(piece)})
        except Exception as e:
            stream_fallback = True
            pl.error(
                f"[PaperWF] report_stream_fail event=report_polish_error node=report detail={e!r} "
                f"used_fallback=true"
            )
            assembled = [raw_fallback]
            await event_queue.put({"type": "content", "data": raw_fallback})

        final_text = "".join(assembled) if assembled else raw_fallback
        out_path = ws / "report.md"
        out_path.write_text(final_text, encoding="utf-8")
        pl.info(
            f"[PaperWF] report_written event=report_end node=report path={out_path} "
            f"chars={len(final_text)} stream_fallback={stream_fallback}"
        )

        # @Step: 2b - 可选：将 report.md 写入向量库（领域 = 工作流 tenant_id）
        if config.paper_report_auto_index_enabled:
            tid_raw = (state.get("tenant_id") or "").strip()
            tid_norm = normalize_tenant_id(tid_raw if tid_raw else None)
            if not tid_raw or tid_norm == "default":
                pl.warning(
                    "[PaperWF] report_auto_index_skip event=report_auto_index_skip "
                    "reason=tenant_default_or_empty"
                )
            else:
                try:
                    from app.services.vector_index_service import vector_index_service

                    embed_n = vector_index_service.index_single_file(
                        str(out_path.resolve()),
                        tenant_id=tid_norm,
                    )
                    pl.info(
                        f"[PaperWF] report_auto_index_ok event=report_auto_index_ok "
                        f"chunk_count={embed_n} tenant_id={tid_norm}"
                    )
                except Exception as ex:
                    pl.warning(
                        f"[PaperWF] report_auto_index_fail event=report_auto_index_fail detail={ex!r}"
                    )

        # @Step: 3 - 完成（对齐参考 completed）
        await event_queue.put(
            {
                "type": "phase",
                "data": {
                    "node": "report",
                    "status": "end",
                    "detail": {
                        "stage": "completed",
                        "path": str(out_path),
                        "chars": len(final_text),
                    },
                },
            }
        )
        return {
            "assembled_report": final_text,
            "final_report_path": str(out_path),
        }

    return report_agent_node
