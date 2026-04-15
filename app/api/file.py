"""文件上传接口模块"""

import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from app.config import config
from app.models.request import UploadLoadRequest
from app.services.upload_staging import (
    new_staging_id,
    remove_staging,
    resolve_staging_file,
    write_staging_blob,
)
from app.services.vector_index_service import vector_index_service
from app.utils.tenant_id import normalize_tenant_id
from loguru import logger

router = APIRouter()

# 文件上传后存储的路径
UPLOAD_DIR = Path("./uploads")
# 支持的文件类型
ALLOWED_TEXT_EXTENSIONS = ["txt", "md"]
ALLOWED_PDF_EXTENSIONS = ["pdf"]
# 单个文件支持最大大小
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _resolve_upload_tenant_id(tenant_id: str) -> str:
    """规范化 tenant；若开启显式领域则拒绝空或 default。"""
    raw = (tenant_id or "").strip()
    normalized = normalize_tenant_id(raw if raw else None)
    if config.rag_require_explicit_tenant_for_upload:
        if not raw or normalized == "default":
            raise HTTPException(
                status_code=400,
                detail="请先选择知识领域：tenant_id 不能为空或为 default",
            )
    return normalized


async def _validate_upload_file(
    file: UploadFile,
    allowed_extensions: list[str],
) -> tuple[bytes, str]:
    """校验扩展名与大小，返回文件字节与规范化文件名。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    safe_filename = _sanitize_filename(file.filename)
    file_extension = _get_file_extension(safe_filename)
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，仅支持: {', '.join(allowed_extensions)}",
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE} 字节）")
    return content, safe_filename


@router.post("/upload/select")
async def upload_select(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
):
    """
    第一阶段：仅将文件写入暂存区，不建向量索引。
    成功后返回 staging_id 与 selected=true，前端可据此允许「开始嵌入」。
    """
    try:
        _ = _resolve_upload_tenant_id(tenant_id)
        content, safe_filename = await _validate_upload_file(file, ALLOWED_TEXT_EXTENSIONS)
        staging_id = new_staging_id()
        write_staging_blob(staging_id, safe_filename, content)
        logger.info(
            f"[INFO][UploadSelect]: staging_id={staging_id} filename={safe_filename} "
            f"tenant_id={tenant_id} size={len(content)}"
        )
        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "staging_id": staging_id,
                    "filename": safe_filename,
                    "size": len(content),
                    "selected": True,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR][UploadSelect]: {e}")
        raise HTTPException(status_code=500, detail=f"select 失败: {e}") from e


@router.post("/upload/load")
async def upload_load(body: UploadLoadRequest):
    """
    第二阶段：将暂存文件复制到 uploads/ 并执行向量索引；成功后删除暂存目录。
    """
    resolved_tenant = _resolve_upload_tenant_id(body.tenant_id)
    logger.info(
        f"[INFO][UploadLoad]: 收到请求 n_staging={len(body.staging_ids)} "
        f"tenant_id={resolved_tenant}"
    )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    success_count = 0
    fail_count = 0

    for sid in body.staging_ids:
        src = resolve_staging_file(sid)
        if src is None:
            fail_count += 1
            items.append({"staging_id": sid, "status": "error", "detail": "暂存不存在或已失效"})
            continue
        dest = UPLOAD_DIR / src.name
        try:
            if dest.exists():
                dest.unlink()
            shutil.copy2(src, dest)
            embed_chunk_count = vector_index_service.index_single_file(
                str(dest),
                tenant_id=resolved_tenant,
            )
            remove_staging(sid)
            success_count += 1
            items.append(
                {
                    "staging_id": sid,
                    "filename": src.name,
                    "status": "ok",
                    "chunk_count": embed_chunk_count,
                }
            )
            logger.info(
                f"[INFO][UploadLoad]: staging_id={sid} -> {dest} "
                f"chunk_count={embed_chunk_count} tenant_id={resolved_tenant}"
            )
        except Exception as e:
            fail_count += 1
            logger.error(f"[ERROR][UploadLoad]: staging_id={sid} err={e}")
            items.append({"staging_id": sid, "status": "error", "detail": str(e)})

    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "message": "success" if fail_count == 0 else "partial_success",
            "data": {
                "success_count": success_count,
                "fail_count": fail_count,
                "items": items,
            },
        },
    )


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
):
    """
    单阶段上传（兼容旧客户端）：保存到 uploads/ 并立即建索引。
    """
    try:
        resolved_tenant = _resolve_upload_tenant_id(tenant_id)
        content, safe_filename = await _validate_upload_file(file, ALLOWED_TEXT_EXTENSIONS)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOAD_DIR / safe_filename
        if file_path.exists():
            logger.info(f"文件已存在，将覆盖: {file_path}")
            file_path.unlink()
        file_path.write_bytes(content)
        logger.info(f"文件上传成功: {file_path}")
        try:
            logger.info(f"开始为上传文件创建向量索引: {file_path}")
            embed_chunk_count = vector_index_service.index_single_file(
                str(file_path),
                tenant_id=resolved_tenant,
            )
            logger.info(f"向量索引创建成功: {file_path}")
            logger.info(
                f"[INFO][Embedding]: 上传文件嵌入分块数 filename={safe_filename} "
                f"chunk_count={embed_chunk_count}"
            )
        except Exception as e:
            logger.error(f"向量索引创建失败: {file_path}, 错误: {e}")

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "filename": safe_filename,
                    "file_path": str(file_path),
                    "size": len(content),
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {e}") from e


@router.post("/index_directory")
async def index_directory(
    directory_path: str = None,
    tenant_id: str = Query("default"),
):
    """
    索引指定目录下的所有文件

    Args:
        directory_path: 目录路径（可选，默认使用 uploads 目录）

    Returns:
        JSONResponse: 索引结果
    """
    try:
        resolved_tenant = _resolve_upload_tenant_id(tenant_id)
        logger.info(f"开始索引目录: {directory_path or 'uploads'}")

        # 执行索引
        result = vector_index_service.index_directory(directory_path, tenant_id=resolved_tenant)

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success" if result.success else "partial_success",
                "data": result.to_dict(),
            },
        )

    except Exception as e:
        logger.error(f"索引目录失败: {e}")
        raise HTTPException(status_code=500, detail=f"索引目录失败: {e}") from e


@router.post("/upload/pdf")
async def upload_pdf_file(
    file: UploadFile = File(...),
    tenant_id: str = Form("default"),
):
    """
    PDF 单阶段上传：保存到 uploads/ 并立即建索引。
    """
    try:
        resolved_tenant = _resolve_upload_tenant_id(tenant_id)
        content, safe_filename = await _validate_upload_file(file, ALLOWED_PDF_EXTENSIONS)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        file_path = UPLOAD_DIR / safe_filename
        if file_path.exists():
            logger.info(f"PDF 文件已存在，将覆盖: {file_path}")
            file_path.unlink()
        file_path.write_bytes(content)
        logger.info(f"PDF 文件上传成功: {file_path}")
        try:
            logger.info(f"开始为 PDF 文件创建向量索引: {file_path}")
            embed_chunk_count = vector_index_service.index_single_file(
                str(file_path),
                tenant_id=resolved_tenant,
            )
            logger.info(f"PDF 向量索引创建成功: {file_path}")
            logger.info(
                f"[INFO][Embedding]: PDF 上传嵌入分块数 filename={safe_filename} "
                f"chunk_count={embed_chunk_count}"
            )
        except Exception as e:
            logger.error(f"PDF 向量索引创建失败: {file_path}, 错误: {e}")

        return JSONResponse(
            status_code=200,
            content={
                "code": 200,
                "message": "success",
                "data": {
                    "filename": safe_filename,
                    "file_path": str(file_path),
                    "size": len(content),
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF 文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 文件上传失败: {e}") from e


def _get_file_extension(filename: str) -> str:
    """
    获取文件扩展名

    Args:
        filename: 文件名

    Returns:
        str: 扩展名（小写，不含点）
    """
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        return parts[1].lower()
    return ""


def _sanitize_filename(filename: str) -> str:
    """
    规范化文件名，去除空格和特殊字符

    Args:
        filename: 原始文件名

    Returns:
        str: 规范化后的文件名
    """
    # 去除空格
    sanitized = filename.replace(" ", "_")
    # 去除其他可能导致问题的字符
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        sanitized = sanitized.replace(char, "_")
    return sanitized
