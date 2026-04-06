科研领航者                                                                                                                   2026.3-2026.4
开源链接：https://github.com/seven-year7/PaperAccept-Agent
项目介绍：基于 Multi-Agent 架构构建科研全链路智能体，打通文献检索、自动化研读与知识沉淀流程，实现科研资产的一站式管理。项目采用领域隔离技术确保检索增强生成（RAG）过程中的上下文纯净度；
技术栈：LangChain、LangGraph、RAG、Plan-Executor、Multi-Agent、MCP、Milvus、Redis
多智能体架构设计：基于 LangGraph 构建科研全链路智能体，打通文献检索、自动化研读与知识沉淀流程。核心 WriteAgent 采用 Planner-Executor-Auditor（计划-执行-审计）层次化模式。
RAG召回优化：针对科研文档设计了 Semantic Chunking 策略（标题增强 + 语义短句切分），解决传统切片导致的语意断裂问题；引入领域参数过滤机制实现知识库检索隔离，确保不同研究方向下的上下文纯净度，召回准确度提升显著。
系统可靠性：设计了统一的 error_finalize 兜底节点与多级降级策略；针对 RAG 检索超时、模型生成异常等边界情况实现平滑回退与自动重试，确保 Agent 长路径工作流下不卡死、无据不强答。
多维记忆管理系统：利用 Redis 实现多轮对话的 Session 状态持久化；构建 Long-term Memory 模块，通过提取并沉淀用户画像（如研究偏好、用户身份等）。
