"""配置管理模块

使用 Pydantic Settings 实现类型安全的配置管理
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# 与「当前工作目录」解耦：无论从哪启动 uvicorn，都读取项目根目录下的 .env
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_PATH),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用配置
    app_name: str = "SuperBizAgent"
    app_version: str = "1.0.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 9900

    # OpenRouter 配置（OpenAI 兼容接口）
    openrouter_api_key: str = ""
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"

    # Milvus 配置
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_timeout: int = 100000  # 毫秒

    # RAG 配置
    rag_top_k: int = 5
    rag_model: str = "qwen-max"  # 使用快速响应模型，不带扩展思考

    # RAG 检索门控（Milvus L2 距离：越小越相似）
    # 说明：不同 embedding 模型/库内容会导致距离分布变化，建议结合观测日志调参。
    rag_retrieve_max_distance: float = 1.0  # top1 距离阈值（绝对门控）
    rag_retrieve_min_gap: float = 0.05  # top2-top1 最小差距（相对门控）
    rag_retrieve_max_avg_distance: float = 1.1  # topK 平均距离上限（可选门控）
    rag_observability_enabled: bool = True  # 是否输出 RAG 观测日志（[INFO][RAG_OBS]）
    # 为 true 时检索对 metadata["tenant_id"] 做 Milvus 预过滤；false 则全库检索（兼容无 tenant_id 的旧数据）
    rag_tenant_isolation_enabled: bool = True
    rag_retrieve_tool_timeout_ms: int = 30000  # 检索工具外层总超时
    rag_milvus_search_timeout_ms: int = 18000  # Milvus 检索超时（小于工具总超时）
    rag_degrade_general_advice_enabled: bool = True  # 降级时是否要求给通用建议
    # 为 true 时每次 retrieve_knowledge 有命中 chunk 则把全文追加写入 rag_recall_dump_md_path（相对项目根）
    rag_recall_dump_md_enabled: bool = False
    rag_recall_dump_md_path: str = "docx/rag_recall_runtime.md"

    # Elasticsearch BM25 + 混合检索（与 Milvus 同 chunk_id 双写）
    rag_hybrid_enabled: bool = False
    elasticsearch_url: str = ""  # 如 http://localhost:9200
    elasticsearch_index: str = "rag_chunks"
    elasticsearch_verify_certs: bool = True
    # 自建 CA / 证书链 PEM 路径（推荐）：校验 TLS 的同时信任自签名，避免 verify_certs=false
    elasticsearch_ca_certs: str = ""
    # 可选：服务端证书 SHA256 指纹（冒号分隔十六进制），与 ca_certs 二选一或配合使用见 ES 文档
    elasticsearch_ssl_assert_fingerprint: str = ""
    elasticsearch_basic_auth_user: str = ""
    elasticsearch_basic_auth_password: str = ""
    rag_hybrid_vec_top_k: int = 15
    rag_hybrid_bm25_top_k: int = 15
    rag_hybrid_rrf_k: int = 60  # 排名阻尼常数 k：贡献项为 weight/(k+rank+1)
    # 混合检索融合权重（关键词 BM25 / 向量）；和不必为 1，仅影响相对占比
    rag_hybrid_vec_weight: float = 0.7
    rag_hybrid_bm25_weight: float = 0.3
    rag_elasticsearch_timeout_ms: int = 12000  # ES 查询超时
    # 为 true 时检索链路打 [INFO][RAG_*_RECALL] 逐条召回（向量路 / BM25 / RRF 融合后），便于调参；日志量较大
    rag_hybrid_recall_detail_log: bool = False
    rag_summary_enabled: bool = True  # 是否启用长对话滚动摘要
    rag_summary_trigger_rounds: int = 10  # 每 N 轮（user+assistant）触发一次摘要
    rag_summary_recent_rounds_for_update: int = 10  # 参与摘要更新的最近轮数窗口
    rag_summary_model: str = "openai/gpt-4o-mini"  # 摘要专用小模型
    rag_summary_max_chars: int = 2000  # 摘要最大长度，防止二次膨胀

    # 文档分块配置
    chunk_max_size: int = 300
    chunk_overlap: int = 50
    # 层级分块（父/子 token，tiktoken 计长）：为 true 时索引走父子切分；检索命中子后按 parent_id 去重展开为父正文
    rag_hierarchical_chunks_enabled: bool = False
    rag_parent_chunk_tokens: int = 512
    rag_parent_chunk_overlap_tokens: int = 128
    rag_child_chunk_tokens: int = 256
    rag_child_chunk_overlap_tokens: int = 56
    # 与 OpenAI 系 embedding 常见一致；若换模型可改为对应 encoding 名
    rag_tokenizer_encoding: str = "cl100k_base"
    # Markdown：# / ## / ### 标题粗分后，章内 SemanticChunker（与 rag_hierarchical_chunks_enabled 互斥，优先本项）
    rag_markdown_semantic_chunk_enabled: bool = False
    rag_semantic_breakpoint_type: str = "percentile"
    rag_semantic_breakpoint_amount: float = 90.0
    rag_semantic_buffer_size: int = 2
    rag_semantic_max_chunk_tokens: int = 850
    rag_semantic_chunk_overlap_tokens: int = 56
    # 为 true 时上传类接口拒绝 tenant_id 为空或 default（内置页「选择领域」）
    rag_require_explicit_tenant_for_upload: bool = True

    # Redis 会话存储配置（RAG）
    redis_url: str = "redis://localhost:6379/0"
    rag_session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 天
    rag_session_max_events: int = 50  # 最多保留事件条数（含 tool/tool_result）
    rag_session_store_system: bool = False  # 是否将 system prompt 入库

    # 长期记忆（Agent.md / Memory.md，落在 long_term_memory_base_path 根目录；每轮可注入上下文）
    long_term_memory_enabled: bool = True
    # 是否向磁盘追加写入（注册 append_long_term_memory）；默认关闭，避免进程无写权限或策略上不允许智能体落盘
    long_term_memory_write_enabled: bool = False
    long_term_memory_base_path: str = "data/long_term_memory"
    long_term_memory_max_chars_per_file: int = 12000  # 单文件上限，超出截断并记 WARN

    # 论文多 Agent 工作流（arXiv + 阅读摘要写作；可选叠加本地知识库检索）
    # 为 true 时向 RAG 对话 Agent 注册 search_arxiv_papers（默认关闭，避免无意触发 arXiv 限流）
    paper_arxiv_tool_enabled: bool = False
    paper_workspace_root: str = "data/paper_workspaces"
    # 论文工作区子目录名：为 true 时用 UTC 时间戳（精确到分），否则用本机本地时间
    paper_workspace_timestamp_utc: bool = False
    # 用户未在工具参数等场景单独指定时，单次 arXiv 检索最多返回条数（降低 429 风险）
    paper_arxiv_max_results: int = 10
    paper_arxiv_query_delay_seconds: float = 3.0
    # arXiv 请求失败重试（限流/网络抖动）
    paper_arxiv_max_retries: int = 3
    paper_arxiv_retry_backoff_seconds: float = 2.0
    paper_read_max_concurrent: int = 4
    paper_section_max_revise_rounds: int = 3
    # 为 true 时章节内保留 Writer→SectionReviewer 多轮小循环；为 false 时每轮 execute 仅每章「检索→写」一次，由全局 writeAudit 统一把关（默认 false，契合 plan→批处理 execute→audit）
    paper_section_local_review_enabled: bool = False
    # 章节写作：未配置 keywords_for_retrieval 时是否用语义片段 fallback 调用知识库（默认 false）
    paper_section_fallback_rag_from_user_request: bool = False
    # 章节内 retrieve_knowledge 的 query 最大字符（过长截断并打 WARN）
    paper_section_rag_query_max_chars: int = 2000
    # 修订轮将审稿意见拼入检索 query 的最大附加长度
    paper_section_revise_rag_comment_max_chars: int = 400
    # 空字符串时复用 rag_model
    paper_model: str = ""
    paper_reading_summary_max_chars: int = 8000
    # 写作子图全局 audit（writeAudit）最大轮次：每轮先整批 execute 再 audit，REVISE 再 execute，最多该次数后强制 OK 结束子图
    paper_writing_max_reviewer_invocations: int = 3
    # Planner 注入阅读摘要、知识库摘录上限（仅当 paper_writing_rag_enabled=true 时知识库摘录非占位）
    paper_planning_reading_max_chars: int = 8000
    paper_planning_knowledge_max_chars: int = 8000
    # Planner 阶段构造 RAG query 的总长度上限（用户+阅读摘要+Replan 大纲关键词等）
    paper_planning_knowledge_query_max_chars: int = 1000
    # 为 true 时 writePlan / writeExecute 调用 retrieve_knowledge；默认 false，写作仅依赖用户需求与阅读摘要
    paper_writing_rag_enabled: bool = False
    # 全局审稿人看到的各章正文拼接总预算（单章截断后累加）
    paper_global_review_max_chars: int = 12000
    # 全局审稿 bundle 每节正文目标最小配额（会随总预算与节数降为 floor(avail/n)）
    paper_global_review_min_chars_per_section: int = 400
    paper_report_stream_max_tokens: int = 4096
    # 为 true 时 report 落盘成功后索引 report.md（tenant_id 规范化后非 default）
    paper_report_auto_index_enabled: bool = False
    # 整图 ainvoke 超时（毫秒）；默认 30 分钟；0 表示不限制
    paper_workflow_timeout_ms: int = 1_800_000
    # 为 true 时 search 节点在 LLM 生成结构化查询后暂停，需 POST /api/paper/confirm_search 通过后才执行 arXiv 检索（默认开启）
    paper_search_human_confirm_enabled: bool = True
    # 等待人工确认的秒数；0 表示无限等待（不推荐生产）
    paper_search_confirm_timeout_sec: int = 3600
    # 为 true 且 confirm 请求带 AdjustmentText 时，用小模型将自然语言合并进 StructuredArxivQuery（在显式覆盖字段之前）
    paper_search_confirm_refiner_enabled: bool = False
    # 检索确认 NL 修订所用模型；空则复用 rag_summary_model
    paper_search_refiner_model: str = ""

    # 统一聊天入口：是否将「论文整图工作流」与 RAG 对话在 /api/chat、/api/chat_stream 分流（默认 false 便于灰度）
    chat_paper_route_enabled: bool = False
    # 强触发论文工作流的子串，逗号或换行分隔；空字符串时使用 chat_intent_router 内置默认词表
    chat_paper_route_keywords: str = ""
    # 未命中规则时是否调用小模型做意图分类（false 时仅规则，适合无密钥测试）
    chat_paper_route_llm_enabled: bool = True
    # LLM 判为 paper_workflow 的最低置信度；低于且未规则命中则走 RAG
    chat_paper_route_confidence_threshold: float = 0.65
    # 意图分类专用模型；空则复用 rag_summary_model
    chat_paper_route_intent_model: str = ""


# 全局配置实例
config = Settings()
