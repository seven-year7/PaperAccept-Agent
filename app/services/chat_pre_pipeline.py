"""
/**
 * @Module: app/services/chat_pre_pipeline.py
 * @Description: 聊天入口前置拦截管线。长期记忆判别由 LLM 结构化抽取完成，按主题逐条落盘。
 * @Interface: PreChatPipeline.run / pre_chat_pipeline
 */
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any, Dict, List, Literal, Protocol

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from loguru import logger
from pydantic import BaseModel, Field

from app.config import config
from app.services.long_term_memory_store import (
    append_user_profile_topic_entries,
    parse_user_profile_topics,
    read_user_profile_markdown,
)


@dataclass(frozen=True)
class PreChatContext:
    """聊天前置上下文。"""

    question: str
    session_id: str
    user_id: str = "default"
    tenant_id: str = "default"


@dataclass(frozen=True)
class MemoryItem:
    """单条记忆候选。"""

    topic: Literal["user_identity", "user_preference", "lessons_learned"]
    content: str
    source: Literal["explicit"] = "explicit"
    confidence: float = 1.0


@dataclass(frozen=True)
class MemoryDecision:
    """策略层输出：本轮是否写入与待写条目集合。"""

    should_write: bool
    items: List[MemoryItem]
    reason: str


@dataclass
class PreChatResult:
    """前置管线执行观测。"""

    interceptor_results: List[dict] = field(default_factory=list)

    def as_log_payload(self) -> dict:
        return {"interceptors": self.interceptor_results}


class MemoryPolicyEngine(Protocol):
    def decide(self, context: PreChatContext) -> MemoryDecision:
        """根据请求上下文判断是否写入长期记忆。"""


class MemorySink(Protocol):
    def write(self, context: PreChatContext, decision: MemoryDecision) -> Dict[str, Any]:
        """执行长期记忆写入。"""


class PreChatInterceptor(Protocol):
    def intercept(self, context: PreChatContext) -> dict:
        """执行前置拦截，返回可观测结果。"""


class _MemoryExtractSchema(BaseModel):
    should_write: bool = Field(..., description="是否存在可长期保存记忆")
    reason: str = Field(default="", description="判别原因或简述")
    user_identity: List[str] = Field(default_factory=list)
    user_preference: List[str] = Field(default_factory=list)
    lessons_learned: List[str] = Field(default_factory=list)


class LLMMemoryPolicy:
    """基于 LLM 的长期记忆抽取策略（仅 LLM，不回退规则）。"""

    memory_extract_prompt = dedent(
        """
        你是一个专业的记忆提取专家，需要从以下对话内容中，提取需要长期保存的核心记忆点。
        要求：
        1. 严格按照以下分类提取，只提取符合分类的内容，不要添加额外信息；
        2. 每个记忆点必须是客观、精准、完整的事实，不得篡改原意，不得添加主观推断；
        3. 过滤掉所有无关闲聊、临时调试信息、重复内容，只保留有长期价值的信息；
        4. 每个记忆点用简洁的一句话描述，不要太长。
        5. 每条记忆都要用肯定句，精准描述，不要用模糊的词语，比如 “尽量”、“大概”、“可能”；

        分类说明：
        - 用户偏好：用户明确表达的习惯、喜好、禁忌、规范要求
        - 经验教训：对话中总结的踩坑经验、最佳实践、注意事项
        - 用户身份：用户的身份信息
        """
    ).strip()

    _SENSITIVE_RE = re.compile(
        r"(api[_-]?key|token|password|passwd|密钥|口令|密码|私钥)",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self._max_capture_chars = int(config.ltm_interceptor_max_capture_chars)
        self._max_items_per_topic = 5
        self._llm = ChatOpenAI(
            model=(config.openrouter_model or "").strip() or "x-ai/grok-4.1-fast",
            api_key=config.openrouter_api_key,  # type: ignore[arg-type]
            base_url=config.openrouter_api_base,
            temperature=0.0,
            streaming=False,
        )
        self._structured_llm = self._llm.with_structured_output(_MemoryExtractSchema)

    def decide(self, context: PreChatContext) -> MemoryDecision:
        # @Step: 1 - 开关与输入校验
        if not config.ltm_interceptor_enabled:
            return MemoryDecision(should_write=False, items=[], reason="interceptor_disabled")

        question = (context.question or "").strip()
        if not question:
            return MemoryDecision(should_write=False, items=[], reason="empty_question")

        # @Step: 2 - LLM 结构化抽取（失败即本轮不写）
        try:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", self.memory_extract_prompt),
                    ("human", "{question}"),
                ]
            )
            chain = prompt | self._structured_llm
            out = chain.invoke({"question": question})
            parsed = out if isinstance(out, _MemoryExtractSchema) else _MemoryExtractSchema.model_validate(out)
        except Exception as e:
            logger.warning(f"[WARN][LTM_INTERCEPTOR]: llm_extract_failed err={e!r}")
            return MemoryDecision(should_write=False, items=[], reason="llm_error")

        if not parsed.should_write:
            return MemoryDecision(should_write=False, items=[], reason=parsed.reason or "llm_skip")

        items = self._build_items(parsed)
        if not items:
            return MemoryDecision(should_write=False, items=[], reason="llm_empty_items")

        return MemoryDecision(
            should_write=True,
            items=items,
            reason=parsed.reason or "llm_extracted",
        )

    def _build_items(self, parsed: _MemoryExtractSchema) -> List[MemoryItem]:
        out: List[MemoryItem] = []
        out.extend(self._topic_items("user_identity", parsed.user_identity))
        out.extend(self._topic_items("user_preference", parsed.user_preference))
        out.extend(self._topic_items("lessons_learned", parsed.lessons_learned))
        return out

    def _topic_items(
        self,
        topic: Literal["user_identity", "user_preference", "lessons_learned"],
        lines: List[str],
    ) -> List[MemoryItem]:
        items: List[MemoryItem] = []
        seen = set()
        for raw in (lines or [])[: self._max_items_per_topic]:
            text = self._sanitize(raw)
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(MemoryItem(topic=topic, content=text))
        return items

    def _sanitize(self, text: str) -> str:
        s = re.sub(r"\s+", " ", (text or "")).strip()
        if not s:
            return ""
        if self._SENSITIVE_RE.search(s):
            return ""
        if len(s) > self._max_capture_chars:
            s = s[: self._max_capture_chars]
        return s


class LongTermMemoryStoreSink:
    """写入适配器：按 topic 逐条落盘，并做同轮/历史去重。"""

    _TOPIC_LABELS: Dict[str, str] = {
        "user_identity": "用户身份",
        "user_preference": "用户偏好",
        "lessons_learned": "经验教训",
    }

    class _DupJudgeSchema(BaseModel):
        is_duplicate: bool = Field(..., description="候选条目是否与同主题已有条目重复")
        reason: str = Field(default="", description="判断依据")

    _dup_judge_prompt = dedent(
        """
        你是长期记忆去重判断器。请基于同一主题下已有记忆与候选记忆，判断候选是否与已有内容语义重复。
        规则：
        1) 只判断重复与否，不改写文本；
        2) 表述不同但事实相同，判定为重复；
        3) 若候选包含新增事实细节且非同义复述，判定为不重复。
        输出字段：is_duplicate, reason。
        """
    ).strip()

    def write(self, context: PreChatContext, decision: MemoryDecision) -> Dict[str, Any]:
        if not decision.should_write:
            return {"attempted": False, "written_count": 0, "failed_count": 0, "reason": decision.reason}
        if not config.long_term_memory_enabled:
            return {"attempted": True, "written_count": 0, "failed_count": 0, "reason": "long_term_memory_disabled"}
        if not config.long_term_memory_write_enabled:
            return {
                "attempted": True,
                "written_count": 0,
                "failed_count": 0,
                "reason": "long_term_memory_write_disabled",
            }
        if config.ltm_interceptor_dry_run:
            return {"attempted": True, "written_count": 0, "failed_count": 0, "reason": "dry_run"}

        existing_text = read_user_profile_markdown(context.user_id)
        existing_topics = parse_user_profile_topics(existing_text)
        written_count = 0
        failed_count = 0
        skipped_dup_count = 0
        rejected_count = 0
        seen = set()
        topic_counts: Dict[str, int] = {"user_identity": 0, "user_preference": 0, "lessons_learned": 0}
        pending_by_topic: Dict[str, List[str]] = {
            "user_identity": [],
            "user_preference": [],
            "lessons_learned": [],
        }

        for item in decision.items:
            normalized = item.content.strip().lower()
            if not normalized:
                continue
            if normalized in seen:
                skipped_dup_count += 1
                continue
            seen.add(normalized)
            topic_entries = existing_topics.get(item.topic, []) + pending_by_topic.get(item.topic, [])
            if self._is_duplicate_with_llm(item.content, topic_entries):
                skipped_dup_count += 1
                continue
            pending_by_topic[item.topic].append(item.content)
            topic_counts[item.topic] = topic_counts.get(item.topic, 0) + 1

        write_out = append_user_profile_topic_entries(context.user_id, pending_by_topic)
        if write_out.get("ok"):
            written_count = int(write_out.get("written_count", 0))
            rejected_count = max(0, sum(len(v) for v in pending_by_topic.values()) - written_count)
        else:
            rejected_count = sum(len(v) for v in pending_by_topic.values())
            failed_count = rejected_count
            return {
                "attempted": True,
                "written_count": 0,
                "failed_count": failed_count,
                "skipped_dup_count": skipped_dup_count,
                "topic_counts": topic_counts,
                "topic_before_count": write_out.get("topic_before_count", {}),
                "topic_after_count": write_out.get("topic_after_count", {}),
                "token_total_before": write_out.get("token_total_before", 0),
                "token_total_after": write_out.get("token_total_after", 0),
                "evicted_count": int(write_out.get("evicted_count", 0)),
                "reason": str(write_out.get("reject_reason", "write_rejected_or_failed")),
            }

        if rejected_count:
            failed_count += rejected_count
        return {
            "attempted": True,
            "written_count": written_count,
            "failed_count": failed_count,
            "skipped_dup_count": skipped_dup_count,
            "topic_counts": topic_counts,
            "topic_before_count": write_out.get("topic_before_count", {}),
            "topic_after_count": write_out.get("topic_after_count", {}),
            "token_total_before": write_out.get("token_total_before", 0),
            "token_total_after": write_out.get("token_total_after", 0),
            "evicted_count": int(write_out.get("evicted_count", 0)),
            "reason": "written" if written_count > 0 and failed_count == 0 else "partial_or_zero_write",
        }

    def _is_duplicate_with_llm(self, candidate: str, existing_in_topic: List[str]) -> bool:
        if not existing_in_topic:
            return False
        try:
            llm = ChatOpenAI(
                model=(config.openrouter_model or "").strip() or "x-ai/grok-4.1-fast",
                api_key=config.openrouter_api_key,  # type: ignore[arg-type]
                base_url=config.openrouter_api_base,
                temperature=0.0,
                streaming=False,
            )
            structured = llm.with_structured_output(self._DupJudgeSchema)
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", self._dup_judge_prompt),
                    (
                        "human",
                        "主题：{topic}\n已有条目：\n{existing}\n\n候选条目：\n{candidate}",
                    ),
                ]
            )
            existing_text = "\n".join(f"- {x}" for x in existing_in_topic[-10:])
            chain = prompt | structured
            out = chain.invoke(
                {
                    "topic": "用户长期记忆主题",
                    "existing": existing_text,
                    "candidate": candidate,
                }
            )
            parsed = (
                out
                if isinstance(out, self._DupJudgeSchema)
                else self._DupJudgeSchema.model_validate(out)
            )
            return bool(parsed.is_duplicate)
        except Exception as e:
            logger.warning(f"[WARN][LTM_INTERCEPTOR]: dup_judge_failed err={e!r}")
            return True


class MemoryWriteInterceptorImpl:
    """长期记忆前置拦截器。"""

    def __init__(self, policy_engine: MemoryPolicyEngine, memory_sink: MemorySink) -> None:
        self._policy = policy_engine
        self._sink = memory_sink

    def intercept(self, context: PreChatContext) -> dict:
        # @Step: 4 - fail-safe：拦截器异常不影响主流程
        try:
            decision = self._policy.decide(context)
            write_result = self._sink.write(context, decision)
            payload = {
                "name": "memory_write_interceptor",
                "model": (config.openrouter_model or "").strip(),
                "decision_reason": decision.reason,
                "should_write": decision.should_write,
                "items_count": len(decision.items),
                "attempted": bool(write_result.get("attempted")),
                "written_count": int(write_result.get("written_count", 0)),
                "failed_count": int(write_result.get("failed_count", 0)),
                "skipped_dup_count": int(write_result.get("skipped_dup_count", 0)),
                "topic_counts": write_result.get("topic_counts", {}),
                "topic_before_count": write_result.get("topic_before_count", {}),
                "topic_after_count": write_result.get("topic_after_count", {}),
                "evicted_count": int(write_result.get("evicted_count", 0)),
                "token_total_before": int(write_result.get("token_total_before", 0)),
                "token_total_after": int(write_result.get("token_total_after", 0)),
                "reject_reason": str(write_result.get("reason", "")),
                "result_reason": str(write_result.get("reason", "")),
            }
            logger.info(f"[INFO][LTM_INTERCEPTOR]: {payload}")
            return payload
        except Exception as e:  # pragma: no cover - 兜底保护
            logger.warning(f"[WARN][LTM_INTERCEPTOR]: failed err={e!r}")
            return {
                "name": "memory_write_interceptor",
                "decision_reason": "interceptor_exception",
                "should_write": False,
                "items_count": 0,
                "attempted": False,
                "written_count": 0,
                "failed_count": 1,
                "skipped_dup_count": 0,
                "topic_counts": {},
                "result_reason": str(e),
            }


class PreChatPipeline:
    """聊天前置管线（可注册多个拦截器）。"""

    def __init__(self, interceptors: List[PreChatInterceptor]) -> None:
        self._interceptors = interceptors

    async def run(self, context: PreChatContext) -> PreChatResult:
        # @Step: 5 - 顺序执行拦截器，稳定输出观测结构
        result = PreChatResult()
        for interceptor in self._interceptors:
            result.interceptor_results.append(interceptor.intercept(context))
        return result


pre_chat_pipeline = PreChatPipeline(
    interceptors=[
        MemoryWriteInterceptorImpl(
            policy_engine=LLMMemoryPolicy(),
            memory_sink=LongTermMemoryStoreSink(),
        )
    ]
)

