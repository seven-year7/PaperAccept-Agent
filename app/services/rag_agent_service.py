"""
/**
 * @Module: app/services/rag_agent_service.py
 * @Description: RAG Agent 服务（对话/流式对话）。会话历史使用 Redis Hash（history_jsonl）存储，不依赖 LangGraph Checkpoint。
 * @Interface: RagAgentService.query / RagAgentService.query_stream / RagAgentService.get_session_history / RagAgentService.clear_session
 */
"""

from __future__ import annotations

import json
import re
import time
from typing import Annotated, Any, AsyncGenerator, Dict, List, Sequence, cast

from langchain.agents import create_agent
from langchain_core.messages import (
    BaseMessage,
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES, add_messages
from loguru import logger
from typing_extensions import TypedDict
from langchain_openai import ChatOpenAI

from app.config import config
from app.tools import (
    get_current_time,
    retrieve_knowledge,
    search_arxiv_papers,
)
from app.services.long_term_memory_store import build_injection_blocks
from app.services.redis_session_store import redis_session_store
from app.utils.rag_request_context import (
    clear_rag_request_context,
    set_rag_request_context,
)

# OpenAI 兼容模型调用，支持通过 base_url 切换到不同服务商（如 DashScope/OpenRouter）


class AgentState(TypedDict):
    """Agent 状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]


def trim_messages_middleware(state: AgentState) -> dict[str, Any] | None:
    """
    修剪消息历史，只保留最近的几条消息以适应上下文窗口

    策略：
    - 保留第一条系统消息（System Message）
    - 保留最近的 6 条消息（3 轮对话）
    - 当消息少于等于 7 条时，不做修剪

    Args:
        state: Agent 状态

    Returns:
        包含修剪后消息的字典，如果无需修剪则返回 None
    """
    messages = list(state["messages"])

    # 如果消息数量较少，无需修剪
    if len(messages) <= 7:
        return None

    # 保留开头连续的 SystemMessage（主 system、长期记忆、摘要等），避免裁剪丢失
    prefix_len = 0
    for i, msg in enumerate(messages):
        if isinstance(msg, SystemMessage):
            prefix_len = i + 1
        else:
            break

    # 保留最近的 6 条消息（确保包含完整的对话轮次）
    recent_messages = messages[-6:] if len(messages) % 2 == 0 else messages[-7:]
    tail_start = len(messages) - len(recent_messages)
    keep_indices = set(range(prefix_len)) | set(range(tail_start, len(messages)))
    new_messages = [messages[i] for i in sorted(keep_indices)]

    logger.debug(f"修剪消息历史: {len(messages)} -> {len(new_messages)} 条")

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *new_messages
        ]
    }


def _extract_degrade_reason_from_tool_content(content: str) -> str:
    """从工具输出中解析降级原因（reason=xxx）。"""
    match = re.search(r"reason=([a-zA-Z_]+)", content or "")
    return match.group(1) if match else ""


def _long_term_memory_obs_from_messages(_messages_result: List[Any]) -> Dict[str, Any]:
    """观测：长期记忆注入与前置拦截器开关状态。"""
    return {
        "ltm_read_enabled": config.long_term_memory_enabled,
        "ltm_write_enabled": config.long_term_memory_write_enabled,
        "ltm_interceptor_enabled": config.ltm_interceptor_enabled,
        "ltm_interceptor_dry_run": config.ltm_interceptor_dry_run,
    }


class RagAgentService:
    """RAG Agent 服务 - 使用 LangGraph + ChatQwen 原生集成"""

    def __init__(self, streaming: bool = True):
        """初始化 RAG Agent 服务

        Args:
            streaming: 是否启用流式输出，默认为 True
        """
        self.model_name = config.rag_model
        self.streaming = streaming
        self.system_prompt = self._build_system_prompt()


        self.model = ChatOpenAI(
            model=self.model_name,
            api_key=cast(Any, config.openrouter_api_key),
            base_url=config.openrouter_api_base,
            temperature=0.7,
            streaming=streaming,
        )
        self.summary_model = ChatOpenAI(
            model=config.rag_summary_model,
            api_key=cast(Any, config.openrouter_api_key),
            base_url=config.openrouter_api_base,
            temperature=0.2,
            streaming=False,
        )

        # 定义基础工具（长期记忆写入由前置拦截器处理，不在 Agent tools 内执行）
        self.tools = [retrieve_knowledge, get_current_time]
        if config.paper_arxiv_tool_enabled:
            self.tools = [*self.tools, search_arxiv_papers]

        # Agent 初始化（会在异步方法中完成）
        self.agent = None
        self._agent_initialized = False

        logger.info(f"RAG Agent 服务初始化完成 (ChatOpenAI), model={self.model_name}, streaming={streaming}")
        logger.info(
            f"[INFO][LTM]: read={config.long_term_memory_enabled} "
            f"write_env={config.long_term_memory_write_enabled} "
            f"interceptor_enabled={config.ltm_interceptor_enabled} "
            f"interceptor_dry_run={config.ltm_interceptor_dry_run} "
            f"（写入在 API 前置拦截器执行）"
        )
        if config.paper_arxiv_tool_enabled:
            logger.info("[INFO][RAG]: paper_arxiv search_arxiv_papers tool registered for chat agent")

    @staticmethod
    def _select_recent_round_events(
        events: List[Dict[str, Any]],
        rounds: int,
    ) -> List[Dict[str, Any]]:
        """选取最近 N 轮 user+assistant 事件用于滚动摘要。"""
        if rounds <= 0:
            return []
        user_count = 0
        selected_reversed: List[Dict[str, Any]] = []
        for event in reversed(events):
            role = str(event.get("role", ""))
            if role in ("user", "assistant"):
                selected_reversed.append(event)
                if role == "user":
                    user_count += 1
                    if user_count >= rounds:
                        break
        return list(reversed(selected_reversed))

    @staticmethod
    def _format_events_for_summary(events: List[Dict[str, Any]]) -> str:
        """将会话事件格式化为摘要模型输入文本。"""
        lines: List[str] = []
        for event in events:
            role = str(event.get("role", ""))
            if role not in ("user", "assistant"):
                continue
            content = str(event.get("content", "")).strip()
            if not content:
                continue
            prefix = "用户" if role == "user" else "助手"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    async def _update_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """使用小模型更新会话滚动摘要（失败不抛错）。"""
        started = time.perf_counter()
        result: Dict[str, Any] = {
            "summary_triggered": False,
            "summary_model": config.rag_summary_model,
            "summary_elapsed_ms": 0.0,
            "summary_round_count": 0,
            "summary_length": 0,
            "summary_error": "",
        }
        if not config.rag_summary_enabled:
            return result
        try:
            events = await redis_session_store.get_events(session_id)
            old_summary = await redis_session_store.get_summary(session_id)
            selected = self._select_recent_round_events(
                events, int(config.rag_summary_recent_rounds_for_update)
            )
            dialog_text = self._format_events_for_summary(selected)
            if not dialog_text.strip():
                return result

            summary_prompt = (
                "你是会话记忆压缩助手。请基于“已有摘要”和“最近对话”输出新的滚动摘要，"
                "仅保留稳定事实与后续有用信息。严格按以下小节输出：\n"
                "1) 已确认事实\n2) 用户偏好与约束\n3) 未决事项\n4) 最近结论与下一步\n"
                f"总长度不超过 {int(config.rag_summary_max_chars)} 字，不要编造。"
            )
            human_content = (
                f"【已有摘要】\n{old_summary or '（无）'}\n\n"
                f"【最近对话】\n{dialog_text}\n"
            )
            summary_resp = await self.summary_model.ainvoke(
                [SystemMessage(content=summary_prompt), HumanMessage(content=human_content)]
            )
            new_summary = str(getattr(summary_resp, "content", "") or "").strip()
            if not new_summary:
                return result
            if len(new_summary) > int(config.rag_summary_max_chars):
                new_summary = new_summary[: int(config.rag_summary_max_chars)]

            current_round_count = await redis_session_store.get_round_count(session_id)
            await redis_session_store.save_summary(
                session_id=session_id,
                summary_text=new_summary,
                rounds_count=current_round_count,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            result.update(
                {
                    "summary_triggered": True,
                    "summary_elapsed_ms": round(elapsed_ms, 2),
                    "summary_round_count": current_round_count,
                    "summary_length": len(new_summary),
                    "summary_error": "",
                }
            )
            return result
        except Exception as e:
            elapsed_ms = (time.perf_counter() - started) * 1000
            result.update(
                {
                    "summary_triggered": True,
                    "summary_elapsed_ms": round(elapsed_ms, 2),
                    "summary_error": str(e),
                }
            )
            logger.warning(f"[WARN][RAG_SUMMARY]: update_failed session={session_id} err={e}")
            return result

    async def _initialize_agent(self):
        """异步初始化 Agent（仅本地工具：检索、时间、可选长期记忆）。"""
        if self._agent_initialized:
            return

        self.agent = create_agent(
            self.model,
            tools=self.tools,
        )

        self._agent_initialized = True

        if self.tools:
            tool_names = [
                tool.name if hasattr(tool, "name") else str(tool) for tool in self.tools
            ]
            logger.info(f"可用工具列表: {', '.join(tool_names)}")

    def _build_system_prompt(self) -> str:
        """
        构建系统提示词

        注意：LangChain 框架会自动将工具信息传递给 LLM，
        因此系统提示词中无需列举具体的工具列表。

        Returns:
            str: 系统提示词
        """
        from textwrap import dedent

        ltm_read = dedent("""
            长期记忆（若已注入 [LONG_TERM_AGENT_RULES] / [LONG_TERM_USER_PROFILE]）：
            - 优先遵守其中的用户约束与画像（语气、禁忌、偏好等）。
            - 【防串题】长期记忆不是事实知识库：不得用其中的爱好、游戏、身份举例等去回答用户当前的事实/技术问题；
              若检索工具已返回「库中无可靠依据」或等价结论，应如实说明无法从知识库回答，可给通用排查框架或请用户补充资料，
              禁止把无关长期记忆（例如别的领域话题）硬扯成当前问题的答案。
        """).strip()
        ltm_write = dedent("""
            - 长期记忆写入由请求入口前置拦截器处理（先于意图识别与 RAG）。
            - 若用户明确要求“记住/保存”，根据拦截器策略进行写入；不要保存密码、令牌等敏感信息。
        """).strip()
        ltm_readonly = dedent("""
            - 当前长期记忆写入链路未开放（或 dry-run），不要声称已将内容保存到服务端长期记忆文件。
        """).strip()

        base = dedent("""
            你是一个专业的AI助手，能够使用多种工具来帮助用户解决问题。

            工作原则:
            1. 理解用户需求，选择合适的工具来完成任务
            2. 当需要获取实时信息或专业知识时，主动使用相关工具
            3. 基于工具返回的结果提供准确、专业的回答
            4. 如果工具无法提供足够信息，请诚实地告知用户
            5. 若知识检索工具返回“库中无可靠依据/低置信命中/未检索到相关资料”，必须明确告知用户“库中无可靠依据”，不得编造；不得用长期记忆或会话里无关话题顶替答案；优先提出澄清问题或说明需要补充资料后再判断。
            6. 若工具结果包含 degraded=true 或“当前知识库暂不可用”，必须明确告知“当前知识库暂不可用，先给通用建议”，不得伪装成已检索成功。

            回答要求:
            - 保持友好、专业的语气
            - 回答简洁明了，重点突出
            - 基于事实，不编造信息
            - 如有不确定的地方，明确说明

            请根据用户的问题，灵活使用可用工具，提供高质量的帮助。
        """).strip()

        if config.long_term_memory_enabled:
            if config.long_term_memory_write_enabled:
                return f"{base}\n\n{ltm_read}\n{ltm_write}"
            return f"{base}\n\n{ltm_read}\n{ltm_readonly}"
        return base

    async def _load_history_messages(self, session_id: str, user_id: str) -> List[BaseMessage]:
        """
        从 Redis 加载会话历史，并转换为 LangChain messages。

        说明：
        - system prompt 默认不入库（由 config.rag_session_store_system 控制）。
        - tool/tool_result 事件以 SystemMessage 形式注入，保证可读且对后续影响较小。
        - 长期记忆 Markdown 在 system 之后、滚动摘要之前按轮注入。
        """
        events = await redis_session_store.get_events(session_id)
        messages: List[BaseMessage] = []

        # system prompt 注入（推荐不入库；如入库则保留第一条 system）
        if not config.rag_session_store_system:
            messages.append(SystemMessage(content=self.system_prompt))
        else:
            # 若入库：先找第一条 system，否则仍注入当前 system_prompt
            system_event = next((e for e in events if e.get("role") == "system"), None)
            if system_event and system_event.get("content"):
                messages.append(SystemMessage(content=str(system_event.get("content"))))
            else:
                messages.append(SystemMessage(content=self.system_prompt))

        # @Step: 长期记忆双 MD（助手规范先于用户画像）
        if config.long_term_memory_enabled:
            uid = (user_id or "").strip() or "default"
            for label, body in build_injection_blocks(uid):
                messages.append(SystemMessage(content=f"[{label}]\n{body}".strip()))

        # 会话滚动摘要（位于长期记忆之后）
        if config.rag_summary_enabled:
            summary_text = await redis_session_store.get_summary(session_id)
            if summary_text:
                messages.append(
                    SystemMessage(content=f"[CONVERSATION_SUMMARY]\n{summary_text}".strip())
                )

        for e in events:
            role = str(e.get("role", ""))
            content = str(e.get("content", ""))
            if not content:
                continue

            if role == "system":
                # 已处理过 system（入库模式下），其余 system 跳过
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
            elif role in ("tool", "tool_result"):
                name = str(e.get("name") or "")
                call_id = str(e.get("call_id") or "")
                prefix = "[TOOL]" if role == "tool" else "[TOOL_RESULT]"
                meta = f" name={name} call_id={call_id}".strip()
                messages.append(SystemMessage(content=f"{prefix}{meta}\n{content}".strip()))
            else:
                # 未知 role：保守作为 system 注入，避免破坏消息序列
                messages.append(SystemMessage(content=f"[EVENT role={role}]\n{content}".strip()))

        # 二次裁剪：避免 Redis 中历史较长导致上下文爆炸（按条数，简单可靠）
        if len(messages) > max(2, config.rag_session_max_events + 1):
            messages = [messages[0]] + messages[-config.rag_session_max_events :]

        return messages

    async def query(
        self,
        question: str,
        session_id: str,
        user_id: str = "default",
        tenant_id: str = "default",
    ) -> str:
        """
        非流式处理用户问题（一次性返回完整答案）

        Args:
            question: 用户问题
            session_id: 会话ID（作为 thread_id）
            user_id: 用户 ID（长期记忆写入审计；会话仍以 session_id 区分）
            tenant_id: 租户 ID（RAG 检索 Milvus 过滤；模拟场景下来自请求体）

        Returns:
            str: 完整答案
        """
        try:
            await self._initialize_agent()

            logger.info(f"[会话 {session_id}] RAG Agent 收到查询（非流式）: {question}")
            request_id = __import__("uuid").uuid4().hex
            set_rag_request_context(
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "question": question,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                }
            )

            # @Step: 1 - 构建消息（system + 历史 + 本轮 user）
            # @Agent_Logic: 不依赖 checkpointer，将历史从 Redis 恢复后再调用 Agent，保证可控与可观测。
            messages = await self._load_history_messages(session_id, user_id)
            messages.append(HumanMessage(content=question))

            # 构建 Agent 输入
            agent_input = cast(Any, {"messages": messages})

            result = await self.agent.ainvoke(
                input=agent_input,
            )

            # 提取最终答案
            messages_result = result.get("messages", [])
            if messages_result:
                tool_messages = [m for m in messages_result if type(m).__name__ == "ToolMessage"]
                used_tool_output = len(tool_messages) > 0
                retrieve_called = any(
                    (getattr(m, "name", "") or "") == "retrieve_knowledge" for m in tool_messages
                )
                # 兼容：部分实现会在 AIMessage 上体现 tool_calls，但 ToolMessage 可能缺失
                if not retrieve_called:
                    retrieve_called = any(
                        (getattr(m, "tool_calls", None) or [])
                        and any((tc.get("name") == "retrieve_knowledge") for tc in getattr(m, "tool_calls", []))
                        for m in messages_result
                    )
                last_message = messages_result[-1]
                answer = last_message.content if hasattr(last_message, 'content') else str(last_message)

                # 记录工具调用
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    tool_names = [tc.get("name", "unknown") for tc in last_message.tool_calls]
                    logger.info(f"[会话 {session_id}] Agent 调用了工具: {tool_names}")

                # @Step: 2 - 写入 Redis 会话事件（user + tool/tool_result(可选) + assistant）
                events_to_append: List[Dict[str, Any]] = []
                if config.rag_session_store_system:
                    # 入库模式：首次写 system
                    existing = await redis_session_store.get_events(session_id)
                    if not any(e.get("role") == "system" for e in existing):
                        events_to_append.append(
                            redis_session_store.new_event(role="system", content=self.system_prompt)
                        )

                events_to_append.append(redis_session_store.new_event(role="user", content=question))

                # tool_call 仅存摘要（不保证能拿到 tool_result 的完整内容）
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    for tc in last_message.tool_calls:
                        tool_name = str(tc.get("name") or "unknown")
                        tool_input = tc.get("args") or tc.get("input") or {}
                        events_to_append.append(
                            redis_session_store.new_event(
                                role="tool",
                                name=tool_name,
                                call_id=str(tc.get("id") or ""),
                                content=f"input={tool_input}",
                            )
                        )

                events_to_append.append(redis_session_store.new_event(role="assistant", content=str(answer)))
                await redis_session_store.append_events(session_id, events_to_append)

                logger.info(f"[会话 {session_id}] RAG Agent 查询完成（非流式）")
                degrade_reason = ""
                for msg in tool_messages:
                    tool_content = str(getattr(msg, "content", "") or "")
                    parsed_reason = _extract_degrade_reason_from_tool_content(tool_content)
                    if parsed_reason:
                        degrade_reason = parsed_reason
                        break

                summary_obs: Dict[str, Any] = {
                    "summary_triggered": False,
                    "summary_model": config.rag_summary_model,
                    "summary_elapsed_ms": 0.0,
                    "summary_round_count": await redis_session_store.get_round_count(session_id),
                    "summary_length": 0,
                    "summary_error": "",
                }
                if final_answer := str(answer).strip():
                    new_round_count = await redis_session_store.incr_round_count(session_id, 1)
                    summary_obs["summary_round_count"] = new_round_count
                    trigger_rounds = max(1, int(config.rag_summary_trigger_rounds))
                    if config.rag_summary_enabled and new_round_count % trigger_rounds == 0:
                        summary_obs = await self._update_conversation_summary(session_id)
                        if not summary_obs.get("summary_round_count"):
                            summary_obs["summary_round_count"] = new_round_count

                if config.rag_observability_enabled:
                    obs = {
                        "request_id": request_id,
                        "session_id": session_id,
                        "question": question,
                        "is_rag_path": retrieve_called,
                        "retrieve_called": retrieve_called,
                        "used_tool_output": used_tool_output,
                        "degrade_reason": degrade_reason,
                        "rag_hierarchical_chunks_enabled": bool(
                            config.rag_hierarchical_chunks_enabled
                        ),
                        **summary_obs,
                        **_long_term_memory_obs_from_messages(messages_result),
                    }
                    logger.info(f"[INFO][RAG_OBS]: {json.dumps(obs, ensure_ascii=False)}")

                return answer

            logger.warning(f"[会话 {session_id}] Agent 返回结果为空")
            return ""

        except Exception as e:
            logger.error(f"[会话 {session_id}] RAG Agent 查询失败（非流式）: {e}")
            raise
        finally:
            clear_rag_request_context()

    async def query_stream(
        self,
        question: str,
        session_id: str,
        user_id: str = "default",
        tenant_id: str = "default",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式处理用户问题（逐步返回答案片段）

        Args:
            question: 用户问题
            session_id: 会话ID（作为 thread_id）
            user_id: 用户 ID（长期记忆写入审计；会话仍以 session_id 区分）
            tenant_id: 租户 ID（RAG 检索 Milvus 过滤；模拟场景下来自请求体）

        Yields:
            Dict[str, Any]: 包含流式数据的字典
                - type: "content" | "tool_call" | "complete" | "error"
                - data: 具体内容
        """
        try:
            await self._initialize_agent()

            logger.info(f"[会话 {session_id}] RAG Agent 收到查询（流式）: {question}")
            request_id = __import__("uuid").uuid4().hex
            set_rag_request_context(
                {
                    "request_id": request_id,
                    "session_id": session_id,
                    "question": question,
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                }
            )

            # @Step: 1 - 构建消息（system + 历史 + 本轮 user）
            messages = await self._load_history_messages(session_id, user_id)
            messages.append(HumanMessage(content=question))

            # 构建 Agent 输入
            agent_input = cast(Any, {"messages": messages})
            answer_chunks: List[str] = []
            tool_events: List[Dict[str, Any]] = []
            used_tool_output = False
            retrieve_called = False
            degrade_reason = ""

            async for token, metadata in self.agent.astream(
                input=agent_input,
                stream_mode="messages",
            ):
                node_name = metadata.get('langgraph_node', 'unknown') if isinstance(metadata, dict) else 'unknown'
                message_type = type(token).__name__

                if message_type in ("AIMessage", "AIMessageChunk"):
                    # 捕获工具调用（可选）：若有 tool_calls，发 SSE tool_call 并记录事件
                    tool_calls = getattr(token, "tool_calls", None)
                    if tool_calls:
                        for tc in tool_calls:
                            tool_name = str(tc.get("name") or "unknown")
                            tool_input = tc.get("args") or tc.get("input") or {}
                            call_id = str(tc.get("id") or "")
                            tool_events.append(
                                redis_session_store.new_event(
                                    role="tool",
                                    name=tool_name,
                                    call_id=call_id,
                                    content=f"input={tool_input}",
                                )
                            )
                            yield {
                                "type": "tool_call",
                                "data": {
                                    "tool": tool_name,
                                    "status": "start",
                                    "input": tool_input,
                                    "call_id": call_id,
                                },
                            }

                    content_blocks = getattr(token, 'content_blocks', None)

                    if content_blocks and isinstance(content_blocks, list):
                        for block in content_blocks:
                            if isinstance(block, dict) and block.get('type') == 'text':
                                text_content = block.get('text', '')
                                if text_content:
                                    answer_chunks.append(text_content)
                                    yield {
                                        "type": "content",
                                        "data": text_content,
                                        "node": node_name
                                    }
                elif message_type == "ToolMessage":
                    # 尽可能捕获工具返回（不同版本字段可能不同，做兼容）
                    used_tool_output = True
                    tool_name = str(getattr(token, "name", "") or "")
                    if tool_name == "retrieve_knowledge":
                        retrieve_called = True
                    call_id = str(getattr(token, "tool_call_id", "") or "")
                    tool_content = str(getattr(token, "content", "") or "")
                    parsed_reason = _extract_degrade_reason_from_tool_content(tool_content)
                    if parsed_reason and not degrade_reason:
                        degrade_reason = parsed_reason
                    if tool_content:
                        tool_events.append(
                            redis_session_store.new_event(
                                role="tool_result",
                                name=tool_name or None,
                                call_id=call_id or None,
                                content=tool_content,
                            )
                        )
                        yield {
                            "type": "tool_call",
                            "data": {
                                "tool": tool_name or "unknown",
                                "status": "end",
                                "output": tool_content,
                                "call_id": call_id,
                            },
                        }

            logger.info(f"[会话 {session_id}] RAG Agent 查询完成（流式）")
            final_answer = "".join(answer_chunks).strip()

            # @Step: 2 - 写入 Redis 会话事件（user + tool/tool_result + assistant）
            events_to_append: List[Dict[str, Any]] = []
            if config.rag_session_store_system:
                existing = await redis_session_store.get_events(session_id)
                if not any(e.get("role") == "system" for e in existing):
                    events_to_append.append(
                        redis_session_store.new_event(role="system", content=self.system_prompt)
                    )
            events_to_append.append(redis_session_store.new_event(role="user", content=question))
            events_to_append.extend(tool_events)
            if final_answer:
                events_to_append.append(redis_session_store.new_event(role="assistant", content=final_answer))
            await redis_session_store.append_events(session_id, events_to_append)

            summary_obs: Dict[str, Any] = {
                "summary_triggered": False,
                "summary_model": config.rag_summary_model,
                "summary_elapsed_ms": 0.0,
                "summary_round_count": await redis_session_store.get_round_count(session_id),
                "summary_length": 0,
                "summary_error": "",
            }
            if final_answer:
                new_round_count = await redis_session_store.incr_round_count(session_id, 1)
                summary_obs["summary_round_count"] = new_round_count
                trigger_rounds = max(1, int(config.rag_summary_trigger_rounds))
                if config.rag_summary_enabled and new_round_count % trigger_rounds == 0:
                    summary_obs = await self._update_conversation_summary(session_id)
                    if not summary_obs.get("summary_round_count"):
                        summary_obs["summary_round_count"] = new_round_count

            if config.rag_observability_enabled:
                obs = {
                    "request_id": request_id,
                    "session_id": session_id,
                    "question": question,
                    "is_rag_path": retrieve_called,
                    "retrieve_called": retrieve_called,
                    "used_tool_output": used_tool_output,
                    "degrade_reason": degrade_reason,
                    "rag_hierarchical_chunks_enabled": bool(
                        config.rag_hierarchical_chunks_enabled
                    ),
                    **summary_obs,
                    "ltm_read_enabled": config.long_term_memory_enabled,
                    "ltm_write_enabled": config.long_term_memory_write_enabled,
                    "ltm_interceptor_enabled": config.ltm_interceptor_enabled,
                    "ltm_interceptor_dry_run": config.ltm_interceptor_dry_run,
                }
                logger.info(f"[INFO][RAG_OBS]: {json.dumps(obs, ensure_ascii=False)}")

            yield {"type": "complete", "data": {"answer": final_answer}}

        except Exception as e:
            logger.error(f"[会话 {session_id}] RAG Agent 查询失败（流式）: {e}")
            yield {
                "type": "error",
                "data": str(e)
            }
            raise
        finally:
            clear_rag_request_context()

    async def get_session_history(self, session_id: str) -> list:
        """
        获取会话历史（从 Redis Hash history_jsonl 读取）

        Args:
            session_id: 会话ID（即 thread_id）

        Returns:
            list: 消息历史列表 [{"role": "user|assistant", "content": "...", "timestamp": "..."}]
        """
        try:
            history = []

            events = await redis_session_store.get_events(session_id)
            for e in events:
                role = str(e.get("role", ""))
                if role == "system":
                    continue
                content = str(e.get("content", ""))
                ts = e.get("ts")
                history.append(
                    {
                        "role": role,
                        "content": content,
                        "timestamp": str(ts) if ts is not None else "",
                    }
                )
            
            logger.info(f"获取会话历史: {session_id}, 消息数量: {len(history)}")
            return history
            
        except Exception as e:
            logger.error(
                f"获取会话历史失败: {session_id}, 错误: {type(e).__name__}: {e}"
            )
            return []

    async def clear_session(self, session_id: str) -> bool:
        """
        清空会话历史（从 Redis 删除）

        Args:
            session_id: 会话ID（即 thread_id）

        Returns:
            bool: 是否成功
        """
        try:
            cleared = await redis_session_store.clear(session_id)
            
            logger.info(f"已清除会话历史: {session_id}")
            return cleared
            
        except Exception as e:
            logger.error(f"清空会话历史失败: {session_id}, 错误: {e}")
            return False

    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("清理 RAG Agent 服务资源...")
            logger.info("RAG Agent 服务资源已清理")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


# 全局单例 - 启用流式输出
rag_agent_service = RagAgentService(streaming=True)
