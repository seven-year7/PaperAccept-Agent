# RAG 混合检索召回日志说明（向量匹配 + BM25 + 加权排名融合）

本文说明：在用户提问并触发 `retrieve_knowledge` 工具时，**从请求进入到最终交给模型的文档列表**，日志里会出现哪些阶段，以及如何阅读：

- **向量匹配（Milvus ANN，L2）** 的召回含义、配置与 `[INFO][RAG_VEC_RECALL]` 字段；
- **BM25（Elasticsearch）** 的逐条命中 `[INFO][RAG_BM25_RECALL]`；
- **加权融合后** 的最终顺序仍打在 `[INFO][RAG_RRF_RECALL]`（Tag 未改，便于兼容旧 grep）。

另补充：**未开启混合检索时**仅走向量路，此时没有 `[INFO][RAG_VEC_RECALL]`，但仍有 Milvus 侧通用 INFO/DEBUG 日志可对照。

---

## 1. 前置条件

| 条件 | 说明 |
|------|------|
| `RAG_HYBRID_ENABLED=true` | 走混合检索：`hybrid_search_documents`（Milvus + ES BM25 + 加权排名融合）。 |
| `ELASTICSEARCH_URL` 等已配置且可连 | BM25 路才有结果；失败时 `es_degraded=true`，等价于仅向量路参与融合。 |
| **`RAG_HYBRID_RECALL_DETAIL_LOG=true`** | **必须打开**，才会输出本文描述的 `[INFO][RAG_VEC_RECALL]` / `[INFO][RAG_BM25_RECALL]` / `[INFO][RAG_RRF_RECALL]` 明细行。 |
| `RAG_OBSERVABILITY_ENABLED=true`（默认） | 额外有一条汇总的 `[INFO][RAG_OBS]` JSON（条数、距离门控等），与明细互补。 |
| `RAG_HIERARCHICAL_CHUNKS_ENABLED=true`（可选） | 索引为父子 token 分块；`[INFO][RAG_OBS]` JSON 会多 `rag_hierarchical_chunks_enabled`；融合后按 `parent_id` 去重展开父正文，**chunk_count** 可能小于融合子条数。 |

在 **项目根 `.env`** 中增加或修改：

```env
RAG_HYBRID_RECALL_DETAIL_LOG=true
```

修改后请 **重启** FastAPI / uvicorn。

---

## 2. 端到端调用链（从提问到日志）

下面按**时间顺序**描述一次典型 RAG 检索（混合开启时）。

### 2.1 用户问题进入对话服务

- 客户端调用 `POST /api/chat` 或 `POST /api/chat_stream`，请求体含 `Question`、`TenantId` 等。
- `RagAgentService` 组装消息，调用 LangGraph Agent；模型决定是否调用工具 `retrieve_knowledge`。

### 2.2 工具入口

- 文件：`app/tools/knowledge_tool.py`  
- 函数：`retrieve_knowledge(query: str)`  
- 首条相关日志（与明细开关无关）：

```text
[INFO][RAG_RETRIEVE]: retrieve_knowledge called request_id=... session_id=... rag_tenant_id=... query='...'
```

其中 `query` 是**模型传入工具的检索语句**（可能与用户原话略有改写）。

- 上下文变量：`get_rag_request_context()` 提供 `request_id`、`session_id`、`tenant_id`，用于租户隔离与日志关联。

### 2.3 检索核心 `_retrieve_core`

- 若 `RAG_HYBRID_ENABLED=true`：调用  
  `vector_search_service.hybrid_search_documents(query, tenant_id)`  
- 否则：仅 `search_similar_documents`（纯 Milvus）。

### 2.4 混合检索内部三阶段（明细日志所在）

实现文件：`app/services/vector_search_service.py` → `hybrid_search_documents`。

| 顺序 | 阶段 | 做什么 | 明细日志 Tag |
|------|------|--------|----------------|
| ① | **向量路（Milvus）** | 对 `query` 做 embedding，L2 ANN，`top_k = RAG_HYBRID_VEC_TOP_K`（默认 15）；可选 `metadata.tenant_id` 过滤。 | `[INFO][RAG_VEC_RECALL]` |
| ② | **BM25 路（Elasticsearch）** | `match` 查询字段 `content`，`size = RAG_HYBRID_BM25_TOP_K`；可选 `tenant_id` term 过滤。 | `[INFO][RAG_BM25_RECALL]` |
| ③ | **加权排名融合** | `app/utils/hybrid_retrieval.py` 中 `weighted_hybrid_fusion_search_results`：向量路贡献 `RAG_HYBRID_VEC_WEIGHT/(k+rank+1)`，BM25 路贡献 `RAG_HYBRID_BM25_WEIGHT/(k+rank+1)`，`k = RAG_HYBRID_RRF_K`；同 `chunk_id` 累加后排序，取前 `RAG_TOP_K` 条。 | `[INFO][RAG_RRF_RECALL]` |

### 2.5 混合路径总览日志 `[INFO][HybridRAG]`（不依赖明细开关）

开启 `RAG_HYBRID_ENABLED` 且走 `hybrid_search_documents` 时，**无论** `RAG_HYBRID_RECALL_DETAIL_LOG` 是否打开，都会打若干行 `[INFO][HybridRAG]`，用于在终端快速确认「不是纯向量」：

1. **进入混合检索**：含 `vec_top_k`、`bm25_top_k`、`final_top_k`、`tenant_id`。  
2. **向量路 + BM25 已召回**：`vec_hits`、`bm25_hits`、`es_degraded`（ES 失败时为 `true`，BM25 条数可能为 0）。  
3. **加权融合完成**：`merged_count`（通常等于 `RAG_TOP_K`，若候选不足则更少）、`vec_w` / `bm25_w`。

随后仍会出现 Milvus 的「开始搜索相似文档 / 搜索完成」（**混合流程的第 ① 步**），因此**不能**仅凭这两行判断为纯向量；应结合 `[INFO][HybridRAG]` 或 `[INFO][RAG_OBS]` 里的 `hybrid_bm25_hits` / `hybrid_es_degraded`。

---

## 3. 如何读 BM25 明细日志 `[INFO][RAG_BM25_RECALL]`

实现文件：`app/services/elasticsearch_chunk_store.py` → `search_bm25`。

### 3.1 汇总行

每条检索会先打一条 **summary**（即使 BM25 命中数为 0）：

```text
[INFO][RAG_BM25_RECALL] summary query="..." tenant_id=... index=rag_chunks bm25_hits=N
```

- **`bm25_hits=N`**：ES 返回的命中条数（在 `size` 限制内）。  
- **`tenant_id`**：规范化后的租户，与 Milvus 检索一致（由 `RAG_TENANT_ISOLATION_ENABLED` 控制是否在 ES 侧 filter）。

### 3.2 逐条命中（phase = bm25_raw）

对每个命中，一行 JSON（单行日志，便于 `grep` / 管道解析）：

```text
[INFO][RAG_BM25_RECALL] {"phase":"bm25_raw","rank":1,"chunk_id":"...","bm25_score":12.34,"source":"...","file_name":"...","tenant_id":"...","content_preview":"..."}
```

| 字段 | 含义 |
|------|------|
| `rank` | BM25 侧排序：1 为 ES 返回的第一条（分数最高）。 |
| `chunk_id` | 与 Milvus 中该分片主键一致，用于融合与向量路去重对齐。 |
| `bm25_score` | Elasticsearch `_score`（BM25 相关度，**不是** 0~1 概率，仅可比排序）。 |
| `source` | 文档来源路径（入库 metadata）。 |
| `file_name` | 文件名（若有）。 |
| `tenant_id` | 分片所属租户。 |
| `content_preview` | 正文前约 240 字符（换行压平），**避免日志爆量**。 |

**调参时**：若 BM25 前几名 `content_preview` 与问题语义明显无关，可检查：分词、索引是否更新、`tenant_id` 是否与上传一致、查询是否被模型改写过短/过长等。

---

## 4. 向量匹配（Milvus）与 `[INFO][RAG_VEC_RECALL]`

实现文件：`app/services/vector_search_service.py` → `search_similar_documents`（混合模式下由 `hybrid_search_documents` **第一步**调用）。

### 4.1 向量匹配在做什么

| 环节 | 说明 |
|------|------|
| **查询向量化** | 使用与入库相同的 embedding 服务（如 `OPENROUTER_EMBEDDING_MODEL`），将工具传入的 `query` 转为稠密向量。 |
| **相似度度量** | Milvus `metric_type=L2`（欧氏距离）。**距离越小 = 向量越近 = 语义越相似**；与 BM25 的 `_score`（越大越好）方向相反。 |
| **ANN 检索** | 在集合字段 `vector` 上做近似最近邻；`param` 中含 `nprobe`（代码中为 10），影响召回与延迟。 |
| **读出字段** | `output_fields`: `id`、`content`、`metadata`（业务键如 `_source`、`_file_name`、`tenant_id` 等，取决于索引写入）。 |

### 4.2 混合模式与纯向量模式的 `top_k`

| 模式 | 向量路 `limit` | 融合后再截断 |
|------|----------------|--------------|
| **`RAG_HYBRID_ENABLED=true`** | `RAG_HYBRID_VEC_TOP_K`（默认 15），先多拉候选供 BM25 与加权融合。 | `weighted_hybrid_fusion_search_results` 取前 `RAG_TOP_K` 条。 |
| **`RAG_HYBRID_ENABLED=false`** | 直接 `RAG_TOP_K`。 | 无 BM25/融合。 |

纯向量模式下**不会**出现 `[INFO][RAG_VEC_RECALL]`（该 Tag 仅在 **混合开启** 且 **`RAG_HYBRID_RECALL_DETAIL_LOG=true`** 时打印）。但仍有两条**通用** Milvus 日志（与明细开关无关）：

```text
开始搜索相似文档, 查询: ..., topK: ..., search_timeout_ms=..., tenant_isolation=..., rag_tenant_id=...
搜索完成, 找到 M 个相似文档, embed_elapsed_ms=..., search_elapsed_ms=..., total_elapsed_ms=...
```

用于确认「本轮向量检索命中条数与耗时」。DEBUG 级别下还可能有：`查询向量生成成功, 维度: ...`。

### 4.3 租户过滤（与 BM25 一致）

`RAG_TENANT_ISOLATION_ENABLED=true` 时，Milvus 带 `expr`，只检索 `metadata["tenant_id"]` 与当前请求规范化租户一致的实体（`app/utils/tenant_id.py` → `build_milvus_tenant_expr`）。  
若对话 `TenantId` 与入库 `tenant_id` 不一致，向量路可能 **0 条**，`[INFO][RAG_VEC_RECALL]` 中 `vec_hits=0`。

### 4.4 `[INFO][RAG_VEC_RECALL]` 汇总行

```text
[INFO][RAG_VEC_RECALL] summary query="..." tenant_id=... vec_top_k=15 vec_hits=M
```

| 字段 | 含义 |
|------|------|
| `query` | 与 `retrieve_knowledge(query)` 一致（模型可能改写）。 |
| `tenant_id` | 规范化后的租户。 |
| `vec_top_k` | 本次 ANN 的 `limit`，即 `RAG_HYBRID_VEC_TOP_K`。 |
| `vec_hits` | Milvus 返回条数（≤ `vec_top_k`）。 |

### 4.5 `[INFO][RAG_VEC_RECALL]` 逐条（phase = vector_raw）

```text
[INFO][RAG_VEC_RECALL] {"phase":"vector_raw","rank":1,"chunk_id":"...","l2_distance":0.85,"source":"...","file_name":"...","tenant_id":"...","content_preview":"..."}
```

| 字段 | 含义 |
|------|------|
| `rank` | ANN 顺序：**1 = L2 最小（最相似）**。 |
| `chunk_id` | 即 Milvus 实体 `id`，与 ES 双写 `chunk_id` 一致，供融合按 id 累加分数。 |
| `l2_distance` | 该 hit 的 L2 距离，**越小越好**；可对照 `content_preview` 判断语义是否贴题。 |
| `source` | `metadata._source` 或 `metadata.source`。 |
| `file_name` / `tenant_id` | 来自 `metadata`。 |
| `content_preview` | 正文前约 **240** 字符（换行压平），**非全文**。 |

### 4.6 与后续加权融合的关系

向量路每个 `chunk_id` 在排名 `rank`（从 0 起）上贡献：

`RAG_HYBRID_VEC_WEIGHT / (RAG_HYBRID_RRF_K + rank + 1)`

BM25 路同理用 `RAG_HYBRID_BM25_WEIGHT`。两路分数按 **同一 `chunk_id` 累加** 后排序，再取 Top-`RAG_TOP_K`。详见第 5 节与 `app/utils/hybrid_retrieval.py` → `weighted_hybrid_fusion_search_results`。

`[INFO][RAG_OBS]` 中的 `distances` / `top1_distance` / `below_threshold`：门控主要在 `knowledge_tool._retrieve_core` 里基于 **向量路 L2** 构造（跳过 `_retrieve_source == bm25` 的项），与融合列表可能不完全同一集合，需对照 `[INFO][RAG_RRF_RECALL]` 理解最终注入模型的顺序。

---

## 5. 如何读加权融合后明细 `[INFO][RAG_RRF_RECALL]`

融合后得到**最终**交给门控与 `format_docs` 的列表（最多 `RAG_TOP_K` 条）。

汇总行示例：

```text
[INFO][RAG_RRF_RECALL] summary query="..." tenant_id=... rank_k=60 vec_w=0.7 bm25_w=0.3 final_top_k=5 merged_count=5 vec_hits=15 bm25_hits=10 es_degraded=false
```

- **`merged_count`**：融合后条数（≤ `RAG_TOP_K`）。  
- **`vec_w` / `bm25_w`**：两路权重（环境变量 `RAG_HYBRID_VEC_WEIGHT` / `RAG_HYBRID_BM25_WEIGHT`）。  
- **`es_degraded`**：ES 异常或未配置 URL 时为 `true`，此时 BM25 路为空，融合实际仅向量路贡献。

逐条：

```text
[INFO][RAG_RRF_RECALL] {"phase":"after_weighted_fusion","rank":1,"chunk_id":"...","retrieve_source":"vector","fusion_score":0.02295,"rrf_score":0.02295,"score_raw":0.91,"score_meaning":"l2_distance_if_vector_else_bm25","source":"...","file_name":"...","content_preview":"..."}
```

| 字段 | 含义 |
|------|------|
| `rank` | **最终**给模型的顺序（1 最先注入上下文）。 |
| `retrieve_source` | `vector`：该 `chunk_id` 在向量路中存在，正文与 L2 来自 Milvus；`bm25`：仅 BM25 路命中（向量路未返回该 id）。 |
| `fusion_score` | 加权融合累加分数，越大越靠前。 |
| `rrf_score` | 与 `fusion_score` 相同，保留旧字段名便于兼容。 |
| `score_raw` | 若 `vector` 则为 **L2 距离**；若 `bm25` 则为 **BM25 分**。 |
| `score_meaning` | 固定说明，避免把两种分数混为一谈。 |

---

## 6. 汇总 JSON：`[INFO][RAG_OBS]`

在 `retrieve_knowledge` 末尾（`RAG_OBSERVABILITY_ENABLED=true`）会打一条 JSON，其中与混合检索相关的字段包括：

- `retrieve_query`：工具收到的 query  
- `rag_tenant_id`  
- `rag_hybrid_enabled`  
- `hybrid_vec_hits` / `hybrid_bm25_hits` / `hybrid_es_degraded`  
- `chunk_count`、`top1_distance`、`below_threshold` 等（门控仍主要基于 **向量路 L2**，纯 BM25 命中无 L2 时门控逻辑见 `knowledge_tool._retrieve_core`）

**明细仍以 `[INFO][RAG_*_RECALL]` 为准**；`[INFO][RAG_OBS]` 适合快速看「这一轮有没有 hit、门控是否过」。

---

## 7. 门控与「有召回但未采用」

即使加权融合已排出 `merged_count` 条，仍可能出现：

- **`below_threshold: true`**（`[INFO][RAG_OBS]`）：向量侧 L2 门控认为置信不足，工具返回「低置信命中」文案，模型不应当事实乱答。  
- **`no_docs`**：融合后列表为空。

若需对照：**先看 `[INFO][RAG_RRF_RECALL]` 是否有 `merged_count`**，再看 `[INFO][RAG_OBS]` 的 `below_threshold`。

---

## 8. 推荐排查命令（项目根）

```bash
# 仅看一次对话相关的向量 / BM25 明细（按 request_id 替换）
grep "710a69dabf4f40c6a5e6349571f0642e" your.log | grep RAG_VEC_RECALL
grep "710a69dabf4f40c6a5e6349571f0642e" your.log | grep RAG_BM25_RECALL

# 同一次请求下看完全链路（含向量 + BM25 + 加权融合）
grep "YOUR_REQUEST_ID" your.log | grep -E "RAG_RETRIEVE|RAG_VEC_RECALL|RAG_BM25_RECALL|RAG_RRF_RECALL|RAG_OBS"

# 未开混合时，可看 Milvus 通用检索行（无 RAG_VEC_RECALL 标签）
grep "YOUR_REQUEST_ID" your.log | grep -E "开始搜索相似文档|搜索完成"
```

Windows PowerShell 可用 `Select-String` 代替 `grep`。

---

## 9. 相关源码索引

| 模块 | 路径 | 职责 |
|------|------|------|
| 工具入口 | `app/tools/knowledge_tool.py` | `retrieve_knowledge`、超时、门控、`[INFO][RAG_OBS]` |
| 混合检索编排 | `app/services/vector_search_service.py` | `search_similar_documents`（向量 ANN）、`hybrid_search_documents`、`[INFO][RAG_VEC_RECALL]`、`[INFO][RAG_RRF_RECALL]` |
| BM25 | `app/services/elasticsearch_chunk_store.py` | `search_bm25`、`[INFO][RAG_BM25_RECALL]` |
| 加权融合 | `app/utils/hybrid_retrieval.py` | `weighted_hybrid_fusion_search_results`（`reciprocal_rank_fusion_search_results` 为等权兼容封装） |
| 正文摘要 | `app/utils/log_preview.py` | `preview_for_log` |
| 配置 | `app/config.py` | `rag_hybrid_*`、`rag_hybrid_recall_detail_log` |

---

## 10. 性能与隐私注意

- **`RAG_HYBRID_RECALL_DETAIL_LOG=true` 会产生大量 INFO 日志**，生产环境建议默认关闭，仅在调参/复现时开启。  
- `content_preview` 已截断，但仍可能含业务敏感片段，日志留存与权限需符合内控要求。
