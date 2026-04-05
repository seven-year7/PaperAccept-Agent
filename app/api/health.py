"""健康检查接口"""

from typing import Any
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.config import config
from app.core.milvus_client import milvus_manager
from loguru import logger

router = APIRouter()


@router.get("/health")
async def health_check():
    
    """健康检查接口
    检查服务状态和数据库连接状态
    
    Returns:
        JSONResponse: 健康检查结果
    """
    # 检查服务基本状态
    health_data: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
        "service": config.app_name,
        "version": config.app_version,
        "status": "healthy"
    }
    
    # 检查 Milvus 连接状态
    try:
        milvus_healthy = milvus_manager.health_check()
        milvus_status: str = "connected" if milvus_healthy else "disconnected"
        milvus_message: str = "Milvus 连接正常" if milvus_healthy else "Milvus 连接异常"
        health_data["milvus"] = {
            "status": milvus_status,
            "message": milvus_message
        }
    except Exception as e:
        logger.warning(f"Milvus 健康检查失败: {e}")
        health_data["milvus"] = {
            "status": "error",
            "message": f"Milvus 检查失败: {str(e)}"
        }

    health_data["elasticsearch"] = {
        "status": "skipped",
        "message": "混合检索未启用或未配置 ELASTICSEARCH_URL",
    }
    if config.rag_hybrid_enabled and (config.elasticsearch_url or "").strip():
        try:
            from app.services.elasticsearch_chunk_store import elasticsearch_chunk_store

            es_ok = elasticsearch_chunk_store.ping()
            if es_ok:
                health_data["elasticsearch"] = {
                    "status": "connected",
                    "message": "Elasticsearch 可达",
                }
            else:
                health_data["elasticsearch"] = {
                    "status": "degraded",
                    "message": "Elasticsearch 不可达（不影响整体 200；混合检索可能仅向量路）",
                }
        except Exception as e:
            logger.warning(f"Elasticsearch 健康检查失败: {e}")
            health_data["elasticsearch"] = {
                "status": "degraded",
                "message": f"Elasticsearch 检查异常: {str(e)}",
            }

    # 判断整体健康状态
    overall_status = "healthy"
    status_code = 200
    
    # 如果 Milvus 不可用，服务不可用
    if health_data["milvus"]["status"] != "connected":
        overall_status = "unhealthy"
        status_code = 503
        health_data["error"] = "数据库不可用"
    
    health_data["status"] = overall_status
    
    return JSONResponse(
        status_code=status_code,
        content={
            "code": status_code,
            "message": "服务运行正常" if overall_status == "healthy" else "服务不可用",
            "data": health_data
        }
    )
