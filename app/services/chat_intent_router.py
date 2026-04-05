"""
/**
 * @Module: app/services/chat_intent_router.py
 * @Description: 统一聊天入口意图路由：固定触发词 + 可选 LLM 结构化分类，区分 RAG 对话与论文整图工作流。
 * @Interface: resolve_chat_intent
 */
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Literal, Sequence, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from app.config import config

# @Step: 1 - 意图标签与对外分支名对齐（SSE route.branch）
ChatIntentName = Literal["general_rag", "paper_workflow"]
RouteBranch = Literal["rag_chat", "paper_workflow"]
ForceRouteMode = Literal["auto", "rag", "paper"]

_INTENT_TO_BRANCH: dict[ChatIntentName, RouteBranch] = {
    "general_rag": "rag_chat",
    "paper_workflow": "paper_workflow",
}


class _LLMIntentSchema(BaseModel):
    """@Agent_Logic: 仅当用户需要「多阶段 arXiv 检索→阅读→写作→报告」完整流水线时标 paper_workflow；随口查一两篇论文用 general_rag。"""

    intent: Literal["general_rag", "paper_workflow"] = Field(
        ...,
        description="general_rag=普通对话或轻量检索；paper_workflow=完整论文调研报告流水线",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="对 intent 的置信度")
    normalized_user_request: str = Field(
        default="",
        description="若 paper_workflow：整理后的完整用户需求（可含主题、时间范围）；否则可空",
    )


@dataclass(frozen=True)
class ChatIntentResult:
    """路由结果，供 API 层写 SSE 与下游调用。"""

    intent: ChatIntentName
    branch: RouteBranch
    confidence: float
    source: Literal["rule", "llm", "forced_rag", "forced_paper"]
    normalized_user_request: str

    def effective_user_request(self, original_question: str) -> str:
        u = (self.normalized_user_request or "").strip()
        return u if u else (original_question or "").strip()


# 内置强触发词（可被 CHAT_PAPER_ROUTE_KEYWORDS 覆盖/追加）
_DEFAULT_PAPER_KEYWORDS: tuple[str, ...] = (
    "论文调研",
    "文献综述",
    "系统调研",
    "完整论文工作流",
    "整图论文",
    "写综述",
    "调研报告",
    "arxiv 调研",
    "arXiv 调研",
    "literature review",
    "survey papers",
    "paper survey workflow",
    "full paper research",
)

# 纯寒暄极短句：强制 RAG，避免误启工作流
_GREETING_EXACT: frozenset[str] = frozenset(
    {
        
    }
)


def _parse_keyword_config(raw: str) -> list[str]:
    # @Step: 2 - 解析环境配置中的触发词列表
    if not (raw or "").strip():
        return list(_DEFAULT_PAPER_KEYWORDS)
    parts = re.split(r"[\n,，;；]+", raw)
    return [p.strip() for p in parts if p.strip()]


def _rule_match_paper(question: str, keywords: Sequence[str]) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    low = q.lower()
    for kw in keywords:
        k = kw.strip()
        if not k:
            continue
        if k.lower() in low:
            return True
    return False


def _rule_force_general_rag(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return True
    if len(q) > 24:
        return False
    return q.lower() in {g.lower() for g in _GREETING_EXACT} or q in _GREETING_EXACT


def _build_intent_llm() -> Any:
    model_name = (config.chat_paper_route_intent_model or "").strip() or config.rag_summary_model
    return ChatOpenAI(
        model=model_name,
        api_key=cast(Any, config.openrouter_api_key),
        base_url=config.openrouter_api_base,
        temperature=0.0,
        streaming=False,
    )


async def _classify_with_llm(question: str) -> _LLMIntentSchema | None:
    # @Step: 3 - 小模型结构化输出；失败返回 None → 上层降级 general_rag
    # @Security: 仅传入用户问题文本，不注入会话历史，降低侧信道与提示注入面
    if not (config.openrouter_api_key or "").strip():
        logger.warning("[WARN][ChatRoute]: skip_llm reason=no_openrouter_api_key")
        return None
    try:
        llm = _build_intent_llm()
        structured = llm.with_structured_output(_LLMIntentSchema)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    dedent(
                        """
                        你是对话路由分类器。根据用户最新一条消息判断应走哪条后端路径。
                        - paper_workflow：用户明确要求「系统性文献/论文调研、多阶段流水线、撰写综述或调研报告、按主题批量检索并产出结构化报告」等需要完整 arXiv 检索→阅读摘要→分章写作→终稿 的场景。
                        - general_rag：普通问答、知识库检索、闲聊、写一段短文等。
                        输出 intent、confidence（0~1）、normalized_user_request（仅当 paper_workflow 时填写整理后的需求，否则留空字符串）。
                        """
                    ).strip(),
                ),
                ("human", "{question}"),
            ]
        )
        chain = prompt | structured
        out = cast(_LLMIntentSchema, await chain.ainvoke({"question": question}))
        return out
    except Exception as e:
        logger.warning(f"[WARN][ChatRoute]: llm_classify_fail detail={e!r}")
        return None


async def resolve_chat_intent(
    question: str,
    *,
    force_route: ForceRouteMode = "auto",
) -> ChatIntentResult:
    """
    融合规则与 LLM 的意图解析。

    策略（写死优先级，便于审计）：
    1. force_route 为 rag/paper 时直接返回对应意图，不调 LLM。
    2. 纯寒暄极短句 → general_rag。
    3. 规则关键词命中 → paper_workflow（强触发优先于后续 LLM 否定，避免漏启流水线）。
    4. 否则若开启 LLM → 结构化分类；confidence 低于阈值 → general_rag。
    5. LLM 关闭或失败 → general_rag。
    """
    q_raw = question or ""
    q = q_raw.strip()

    if force_route == "rag":
        logger.info("[INFO][ChatRoute]: force_route=rag")
        return ChatIntentResult(
            intent="general_rag",
            branch="rag_chat",
            confidence=1.0,
            source="forced_rag",
            normalized_user_request="",
        )
    if force_route == "paper":
        logger.info("[INFO][ChatRoute]: force_route=paper")
        return ChatIntentResult(
            intent="paper_workflow",
            branch="paper_workflow",
            confidence=1.0,
            source="forced_paper",
            normalized_user_request=q,
        )

    if _rule_force_general_rag(q):
        logger.info("[INFO][ChatRoute]: rule_greeting_short -> general_rag")
        return ChatIntentResult(
            intent="general_rag",
            branch="rag_chat",
            confidence=1.0,
            source="rule",
            normalized_user_request="",
        )

    keywords = _parse_keyword_config(config.chat_paper_route_keywords)
    if _rule_match_paper(q, keywords):
        logger.info("[INFO][ChatRoute]: rule_keyword -> paper_workflow")
        return ChatIntentResult(
            intent="paper_workflow",
            branch="paper_workflow",
            confidence=1.0,
            source="rule",
            normalized_user_request=q,
        )

    if not config.chat_paper_route_llm_enabled:
        logger.info("[INFO][ChatRoute]: llm_disabled -> general_rag")
        return ChatIntentResult(
            intent="general_rag",
            branch="rag_chat",
            confidence=1.0,
            source="rule",
            normalized_user_request="",
        )

    llm_out = await _classify_with_llm(q)
    if llm_out is None:
        logger.info("[INFO][ChatRoute]: llm_fail_fallback -> general_rag")
        return ChatIntentResult(
            intent="general_rag",
            branch="rag_chat",
            confidence=0.0,
            source="llm",
            normalized_user_request="",
        )

    thr = float(config.chat_paper_route_confidence_threshold)
    intent: ChatIntentName = llm_out.intent
    conf = float(llm_out.confidence)
    if intent == "paper_workflow" and conf < thr:
        logger.info(
            f"[INFO][ChatRoute]: llm_below_threshold conf={conf} thr={thr} -> general_rag"
        )
        intent = "general_rag"

    norm = (llm_out.normalized_user_request or "").strip()
    if intent == "paper_workflow":
        if not norm:
            norm = q
    else:
        norm = ""

    branch = _INTENT_TO_BRANCH[intent]
    logger.info(
        f"[INFO][ChatRoute]: llm intent={intent} conf={conf} branch={branch}"
    )
    return ChatIntentResult(
        intent=intent,
        branch=branch,
        confidence=conf,
        source="llm",
        normalized_user_request=norm if intent == "paper_workflow" else "",
    )
