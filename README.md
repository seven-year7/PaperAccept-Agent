<h1 align="center">SuperBizAgent：RAG 知识库与智能学术调研</h1>

<p align="center">
面向科研场景的多智能体调研系统（RAG+LangGraph+流式论文工作流）
</p>

<p align="center">
<a href="#-简介">简介</a> ·
<a href="#-核心特性">核心特性</a> ·
<a href="#系统架构">系统架构</a> ·
<a href="#工作流程">工作流程</a> ·
<a href="#-快速开始">快速开始</a> ·
<a href="#技术栈">技术栈</a>
</p>


---

## 📖 简介

这是一款面向**研究生与科研场景**的智能体系统：把「找论文、读论文、记要点、跨文献思考」串成一条闭环。用户可以用自然语言**检索并拉取文献**（如arXiv等来源），并对论文**自动阅读、抽取与总结**，减少手工下载与通读全文的时间成本。

针对**「读完一篇忘一篇」**的痛点，系统将阅读过程中沉淀的**核心观点、方法要点**等写入**向量知识库**，支持后续**语义检索与问答**。这样在**同一研究方向**下，可以把多篇文献的要点**放在一起对照**，更容易发现**交叉启发与创新切入点**。

同时实现**领域**：不同课题、不同方向可以维护**相互独立的知识库**，检索时**不会混入无关领域的片段**，避免「搜到一堆用不上的知识」干扰判断，保证对话与调研都建立在**当前方向的有效上下文**之上。

---

## ✨ 核心特性

- 🤖 **多智能体架构设计**：基于 LangGraph 构建科研全链路智能体，打通文献检索、自动化研读与知识沉淀流程。核心 WriteAgent 采用 Planner-Executor-Auditor（计划-执行-审计）层次化模式。
- 📚 **RAG 召回优化**：针对科研文档设计了 SemanticChunking 策略（标题增强 + 语义短句切分），解决传统切片导致的语义断裂问题；引入领域参数过滤机制实现知识库检索隔离，确保不同研究方向下的上下文纯净度，召回准确度提升显著。
- 🛡️ **系统可靠性**：设计了统一的 `error_finalize` 兜底节点与多级降级策略；针对 RAG 检索超时、模型生成异常等边界情况实现平滑回退与自动重试，确保 Agent 长路径工作流下不卡死、无据不强答。
- 💾 **多维记忆管理系统**：利用 Redis 实现多轮对话的 Session 状态持久化；构建 Long-termMemory 模块，通过提取并沉淀用户画像（如研究偏好、用户身份等）。

---

## 系统架构

**简要说明**：实现上采用 **感知 -> 认知 -> 行动 -> 交互** 四层模型（见附录 **A**）。论文链路在 `app/agent/paper/` 由 LangGraph 编排：`search -> reading -> write -> report`，其中 `write` 为子图（`writePlan -> writeExecute -> writeAudit`，`REPLAN` 回到子图内 `writePlan`，`REVISE` 回到 `writeExecute`），失败经 `error_finalize` 兜底。RAG 与论文写作可选叠加 `retrieve_knowledge`（`PAPER_WRITING_RAG_ENABLED`）。

更细的节点职责、条件函数与SSE语义，见附录**A**与**D**（API），源码入口：`app/agent/paper/graph.py`、`write_subgraph.py`、`condition_handler.py`。

---

## 工作流程

### RAG 对话（概要）

1. 客户端携带 `Id`（会话）、`Question`、`TenantId` 等调用 `POST /api/chat_stream`。
2. 请求先经过前置拦截器（可选长期记忆写入）后，再注入系统提示、长期记忆读取内容、Redis 历史与摘要窗口。
3. 模型按需调用 `retrieve_knowledge`；门控/混合检索/降级逻辑在工具内完成。
4. 回复以 SSE 流式返回，并回写 Redis 事件流。

### 论文调研整图（概要）

1. **输入**：自然语言需求（经统一路由或直连 `POST /api/paper/research_stream`）。
2. **检索**：LLM 生成 `StructuredArxivQuery`；若开启人工确认则推送 `search_confirm` 并阻塞至 `confirm_search`。
3. **阅读**：并行阅读多篇 arXiv 条目，结构化抽取并写入 `readings.md` 等。
4. **写作子图**：首步大纲规划（SSE `phase.node` 为 `writePlan`），再批量章节执行与全局审稿循环；`REPLAN` 在子图内重跑 `writePlan`；可选章节内本地多轮审稿。
5. **报告**：合并章节并流式润色，落盘 `report.md`；可选 `PAPER_REPORT_AUTO_INDEX_ENABLED` 写入向量库。

---

## 📂 目录结构

```text
Agent-Create/（或你的项目根目录）
├──app/
│├──main.py#FastAPI应用入口、静态挂载、路由注册、生命周期
│├──config.py#PydanticSettings，从项目根.env加载全部运行时配置
│├──__init__.py
││
│├──api/#HTTP路由层（薄封装，业务在services/agent）
││├──chat.py#/api/chat、/api/chat_stream、会话查询与清空
││├──file.py#/api/upload、/api/upload/pdf、select、load、index_directory
││├──paper.py#/api/paper/research_stream、confirm_search（SSE）
││├──health.py#健康检查
││└──__init__.py
││
│├──agent/#LangGraph等业务编排（当前主要为论文工作流）
││├──__init__.py
││└──paper/
││├──graph.py#主图：search→reading→write→report
││├──write_subgraph.py#写作子图：writePlan→writeExecute→writeAudit；REPLAN、REVISE
││├──condition_handler.py#各车间结束后的下一跳路由、错误进入error_finalize
││├──state.py#论文状态TypedDict/字段定义
││├──schemas.py#StructuredArxivQuery、ReadingExtract等Pydantic模型
││├──node_guard.py#节点软失败包装（登记*_node_error）
││├──llm_utils.py#论文链路共用LLM调用辅助
││├──reading_sanitize.py#阅读正文清洗与readings.md合并排序
││├──__init__.py
││├──nodes/#主图车间节点实现
│││├──search_node.py
│││├──reading_node.py
│││├──writing_plan_node.py#大纲规划（子图节点writePlan）
│││├──writing_execute_node.py#子图writeExecute
│││├──writing_reviewer_node.py
│││├──report_node.py
│││├──error_finalize_node.py#兜底说明与done语义
│││└──__init__.py
││└──write/#写作子图内部
││├──__init__.py
││└──agents/
││├──plan_agent.py#大纲/规划侧逻辑
││├──execute_runner.py#章节执行与可选章节内审稿循环
││├──global_reviewer_agent.py#全局审稿bundle
││└──__init__.py
││
│├──core/#LLM工厂、Milvus客户端等基础设施
│├──services/#RAG、向量索引/检索/嵌入、分片、Redis会话、长期记忆、论文工作流与search_confirm等
│├──tools/#LangChain@tool，供RAGAgent调用
││├──knowledge_tool.py#retrieve_knowledge：Milvus/混合、门控、降级、format_docs
││├──time_tool.py#get_current_time
││├──long_term_memory_tool.py#历史工具写入实现（兼容保留，当前主链路使用前置拦截器）
││├──paper_arxiv_tool.py#可选RAG内arXiv工具（与论文search节点检索器分离）
││└──__init__.py
││
│├──models/#API请求/响应与文档相关模型
││├──request.py
││├──response.py
││├──document.py
││└──__init__.py
││
│└──utils/#租户与混合检索融合、RAG上下文/召回落盘、论文日志等横切工具
│
├──static/#内置Web：index.html、app.js、styles.css
├──tests/#单元与集成测试（论文Mock/Live等）
├──scripts/#Milvus、ES、arXiv、召回导出等烟测脚本
├──docs/#如rag_hybrid_recall_logging.md
├──data/#长期记忆、论文工作区、预览产物（部分宜.gitignore）
├──aiops-docs/#示例知识文档
├──vector-database.yml#Milvus等容器编排
├──start-windows.bat、stop-windows.bat
├──Makefile
├──pyproject.toml、requirements.txt、uv.lock（若使用）
└──README.md
```

---

## 🚀 快速开始

1. **环境**：Python **3.11+**（见 `pyproject.toml` 的 `requires-python`）；建议虚拟环境。
2. **安装依赖**：
```bash
pip install -r requirements.txt
# 或：uv sync / poetry install（若你使用对应工具）
```
3. **配置**：复制并编辑项目根目录 `.env`（至少配置 `OPENROUTER_API_KEY` 等；Milvus/Redis/ES 按实际部署填写）。`.env` 由 `app/config.py` 从 **项目根** 加载，与启动工作目录无关。
4. **启动依赖服务**：`vector-database.yml` 启动 Milvus（及可选组件）；Redis 用于会话历史。
5. **启动 API**：
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9900
```
Windows 可使用 `.\start-windows.bat`；Linux/macOS 可用 `make init` / `make start`（见附录 **C**）。
6. **访问**：Web `http://localhost:9900/`；OpenAPI `http://localhost:9900/docs`。

---

## 配置说明（摘要）

- **模型与嵌入**：`OPENROUTER_API_KEY`、`OPENROUTER_API_BASE`、`OPENROUTER_MODEL`、`OPENROUTER_EMBEDDING_MODEL` 等。
- **Milvus**：`MILVUS_HOST`、`MILVUS_PORT` 等。
- **RAG**：`RAG_TOP_K`、分块与层级/语义 Markdown 开关、`RAG_HYBRID_*`、`REDIS_URL`、租户隔离、召回落盘等。
- **论文工作流**：`PAPER_*` 系列（arXiv 条数/重试、人工确认、写作 RAG、工作区根目录与时间戳、超时等）。

**完整变量表与默认值**见附录**B**（与原手册第6节一致）。

---

## 技术栈

### 后端

- **语言**：Python 3.11+
- **Web**：FastAPI、Uvicorn、`sse-starlette`
- **Agent/编排**：LangChain、**LangGraph**（论文主图与子图）
- **模型**：OpenAI 兼容 API（如 OpenRouter）
- **向量库**：Milvus 2.x；可选 **Elasticsearch** 混合检索
- **会话**：Redis（`history_jsonl` 事件流 + 可选摘要字段）
- **其他**：PydanticSettings、Loguru、httpx、aiohttp、`arxiv` 包等

### 前端（内置）

- 静态页 **HTML+CSS+JS**（`static/`），对话走 **`POST /api/chat_stream`**；工具菜单含领域选择、`txt/md` 上传与独立 PDF 上传（`POST /api/upload/pdf`）。

---

## 贡献指南

欢迎通过Issue/PullRequest改进代码与文档。提交前建议：

- 运行相关测试：`pytest tests/ -o addopts=`（按需加标记排除集成测）。
- 大型行为变更请同步更新本 README 与 `app/config.py` 注释或 `docs/` 下专题文档。

---

## 许可证与联系方式

- **许可证**：若仓库根目录包含 `LICENSE` 文件，以该文件为准；否则请在根目录补充许可证声明。
- **问题反馈**：优先使用仓库 Issues。

---

# 附录 A：架构设计（4-Layer）与实施阶段

## A.1 技术选型（简表）

|组件|选型|作用|
|:---|:---|:---|
|**Web/API**|FastAPI+Uvicorn|HTTP、SSE、静态页面|
|**Agent编排**|LangChain+LangGraph|RAG工具调用；论文工作流状态机|
|**模型接入**|`langchain_openai.ChatOpenAI`（兼容端点）|对话、摘要、论文各节点|
|**向量数据库**|Milvus（`vector-database.yml`）|分片向量存储与检索|
|**会话**|RedisHash|事件流与摘要|

## A.2 感知/认知/行动/交互（摘录）

- **感知**：用户请求、`.md/.txt/.pdf` 上传；`DocumentSplitterService` 分片；`VectorIndexService` 写入 Milvus。
- **认知**：`RagAgentService` 构建 Agent 与消息历史；Redis 持久化；可选滚动摘要。
- **行动**：`retrieve_knowledge`、`get_current_time`（长期记忆写入由前置拦截器处理）。
- **交互**：REST + SSE；内置 `static/`；OpenAPI `/docs`。

## A.3 实施阶段与验证（摘录）

- **阶段一**：上传/索引/检索链路；日志 `[INFO][Embedding]`。
- PDF 上传接口：`POST /api/upload/pdf`（仅 `.pdf`，与文本上传接口分离）；PDF 解析走 Docling（`DocumentConverter.convert` + `export_to_markdown`）后进入既有分块链路；当前不含 OCR，扫描版图片 PDF 可能无法得到有效分块。
- **阶段二**：流式对话、Redis 历史、长期记忆、多租户；验证 `chat_stream` 与工具事件。

（更完整段落与原文一致时，可直接对照版本库Git历史中README细表。）

---

# 附录 B：配置与环境变量（完整）

以下配置项定义于 `app/config.py`（通过项目根 `.env` 加载）：

-**应用**：`APP_NAME`、`APP_VERSION`、`HOST`、`PORT`
-**模型与嵌入**：`OPENROUTER_API_KEY`、`OPENROUTER_API_BASE`、`OPENROUTER_MODEL`、`OPENROUTER_EMBEDDING_MODEL`；嵌入烟测`pythonscripts/test_openrouter_embedding.py`；**对话（与RAG同KEY/BASE/RAG_MODEL）烟测**`pythonscripts/test_openrouter_chat.py`（可选`pythonscripts/test_openrouter_chat.py--also-summary`）
-**Milvus**：`MILVUS_HOST`、`MILVUS_PORT`、`MILVUS_TIMEOUT`；烟测`pythonscripts/test_milvus_connection.py`
-**RAG**：`RAG_TOP_K`、`RAG_MODEL`、`CHUNK_MAX_SIZE`、`CHUNK_OVERLAP`；**层级分块**`RAG_HIERARCHICAL_CHUNKS_ENABLED`与tiktoken参数；**语义Markdown分块**`RAG_MARKDOWN_SEMANTIC_CHUNK_ENABLED`与`RAG_SEMANTIC_*`；**上传显式领域**`RAG_REQUIRE_EXPLICIT_TENANT_FOR_UPLOAD`；**Redis**`REDIS_URL`、`RAG_SESSION_TTL_SECONDS`、`RAG_SESSION_MAX_EVENTS`、`RAG_SESSION_STORE_SYSTEM`；**L1近窗缓存**`RAG_SESSION_L1_ENABLED`、`RAG_SESSION_L1_MAX_SESSIONS`、`RAG_SESSION_L1_RECENT_ROUNDS`、`RAG_SESSION_L1_TTL_SECONDS`；**租户**`RAG_TENANT_ISOLATION_ENABLED`；**召回导出**`pythonscripts/dump_rag_recall.py`；**混合检索**`RAG_HYBRID_ENABLED`、`ELASTICSEARCH_*`、`RAG_HYBRID_*`、`pythonscripts/test_elasticsearch_connection.py`；**长期记忆**`LONG_TERM_MEMORY_*`、`LTM_INTERCEPTOR_*`

长期记忆拦截器灰度建议：
- `LTM_INTERCEPTOR_ENABLED=true` + `LTM_INTERCEPTOR_DRY_RUN=true`：仅打日志不落盘，用于观察命中质量。
- 观察稳定后将 `LTM_INTERCEPTOR_DRY_RUN=false`：开启真实写入。
- 需要快速回滚时仅设置 `LTM_INTERCEPTOR_ENABLED=false`。
- 判别模型使用 `OPENROUTER_MODEL`（建议 `x-ai/grok-4.1-fast`），按三类结构化抽取：`用户身份`、`用户偏好`、`经验教训`。
- 抽取结果为逐条写入（split），并执行同轮去重 + 与现有 `Memory.md` 简单去重；LLM 失败时本轮不写入（不回退规则）。
- `Memory.md` 写入前会按主题加载并判重；同一主题最多保留 `LTM_TOPIC_MAX_ITEMS`（默认 10）条，超过按 FIFO 删除最早条目。
- 整个 `Memory.md` 在写前/写后预测都受 `LTM_MEMORY_MAX_TOKENS`（默认 3000）门控，超限则拒绝新增。
- token 计数使用 `LTM_TOKEN_COUNTER_MODE`：`tiktoken`（优先）或 `approx`（回退字符估算）。
-**论文工作流**：`PAPER_ARXIV_TOOL_ENABLED`、`PAPER_WORKSPACE_ROOT`、`PAPER_WORKSPACE_TIMESTAMP_UTC`、`PAPER_ARXIV_*`、`PAPER_WRITING_RAG_ENABLED`、`PAPER_READ_MAX_CONCURRENT`、`PAPER_SECTION_*`、`PAPER_GLOBAL_REVIEW_*`、`PAPER_MODEL`、`PAPER_READING_SUMMARY_MAX_CHARS`、`PAPER_REPORT_STREAM_MAX_TOKENS`、`PAPER_REPORT_AUTO_INDEX_ENABLED`、`PAPER_WORKFLOW_TIMEOUT_MS`、`StructuredArxivQuery`字段说明、`PAPER_SEARCH_HUMAN_CONFIRM_ENABLED`与`confirm_search`/`PAPER_SEARCH_CONFIRM_*`、**助手消息分段**`assistant_message_boundary`、SSE失败语义等

（完整分项说明、默认值与注意事项与原README「##6.配置与环境变量」逐条一致；篇幅过长处请以`app/config.py`为准。）

---

# 附录 C：启动方式与访问地址

**Windows**：`.\start-windows.bat`（虚拟环境、Milvus、FastAPI、可选示例文档上传）。

**Linux/macOS**：

```bash
make init # 或 make start
make stop
```

**访问**：

-Web：`http://localhost:9900/`
-API文档：`http://localhost:9900/docs`
-健康检查：`http://localhost:9900/health`
-Attu（若随编排启动）：`http://localhost:8000`

---