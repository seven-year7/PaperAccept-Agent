"""请求数据模型

定义 API 请求的 Pydantic 模型
"""

from typing import List, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """对话请求"""

    id: str = Field(..., description="会话 ID", alias="Id")
    question: str = Field(..., description="用户问题", alias="Question")
    user_id: str = Field(
        default="default",
        description="用户 ID（长期记忆为全局共享文件；此字段用于工具写入 meta 审计等；缺省为 default）",
        alias="UserId",
    )
    tenant_id: str = Field(
        default="default",
        description="租户 ID（RAG 知识库隔离；无登录时由客户端模拟；缺省为 default）",
        alias="TenantId",
    )
    force_route: Literal["auto", "rag", "paper"] = Field(
        default="auto",
        description="意图分流：auto=规则+LLM；rag=强制 RAG 对话；paper=强制论文整图（需 chat_stream）",
        alias="ForceRoute",
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "Id": "session-123",
                "Question": "什么是向量数据库？",
                "UserId": "user-001",
                "TenantId": "acme",
                "ForceRoute": "auto",
            }
        }


class UploadLoadRequest(BaseModel):
    """将 /upload/select 暂存的文件正式写入向量库（可多 staging_id 一次提交）"""

    staging_ids: List[str] = Field(..., min_length=1, description="select 返回的暂存 ID 列表")
    tenant_id: str = Field(default="default", description="写入 metadata 的租户，与对话 TenantId 一致")

    class Config:
        json_schema_extra = {
            "example": {
                "staging_ids": ["550e8400-e29b-41d4-a716-446655440000"],
                "tenant_id": "default",
            }
        }


class ClearRequest(BaseModel):
    """清空会话请求"""

    session_id: str = Field(..., description="会话 ID", alias="sessionId")

    class Config:
        populate_by_name = True


class PaperSearchConfirmRequest(BaseModel):
    """人工确认或修改结构化 arXiv 查询后继续检索。"""

    run_id: str = Field(..., description="SSE 事件中返回的 run_id", alias="RunId")
    approved: bool = Field(default=True, description="是否同意按当前条件检索", alias="Approved")
    querys: List[str] | None = Field(
        default=None,
        description="可选：覆盖 LLM 生成的关键词列表（Approved=true 时生效）",
        alias="Querys",
    )
    start_date: str = Field(default="", description="可选覆盖 YYYY-MM-DD", alias="StartDate")
    end_date: str = Field(default="", description="可选覆盖 YYYY-MM-DD", alias="EndDate")
    title_phrase: str | None = Field(
        default=None,
        description="可选：非空时覆盖 arXiv ti: 标题短语",
        alias="TitlePhrase",
    )
    author: str | None = Field(
        default=None,
        description="可选：非空时覆盖 au: 作者",
        alias="Author",
    )
    categories: List[str] | None = Field(
        default=None,
        description="可选：非空列表时覆盖 arXiv 分类",
        alias="Categories",
    )
    sort_mode: Literal["relevance", "submitted_date"] | None = Field(
        default=None,
        description="可选：覆盖排序 relevance / submitted_date",
        alias="SortMode",
    )
    adjustment_text: str = Field(
        default="",
        description="可选：自然语言修订说明（需 PAPER_SEARCH_CONFIRM_REFINER_ENABLED=true；先于显式字段合并，再由表单字段覆盖）",
        alias="AdjustmentText",
    )
    reason: str = Field(default="", description="Approved=false 时可填拒绝原因", alias="Reason")

    class Config:
        populate_by_name = True


class PaperResearchStreamRequest(BaseModel):
    """论文多 Agent 工作流（SSE）"""

    user_request: str = Field(..., description="用户自然语言需求", alias="UserRequest")
    session_id: str = Field(default="paper_default", description="会话 ID", alias="SessionId")
    tenant_id: str = Field(default="default", description="RAG 租户", alias="TenantId")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "UserRequest": "调研近一年关于大模型 RAG 的论文进展",
                "SessionId": "paper-session-1",
                "TenantId": "default",
            }
        }
