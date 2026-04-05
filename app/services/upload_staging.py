"""
@Module: app/services/upload_staging.py
@Description: 两阶段上传（/upload/select → /upload/load）的磁盘暂存，按 UUID 目录隔离
@Interface: write_staging_blob / resolve_staging_file / remove_staging
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

STAGING_PARENT = Path("./uploads/staging")


def new_staging_id() -> str:
    return str(uuid.uuid4())


def _parse_staging_id(raw: str) -> str | None:
    try:
        return str(uuid.UUID(raw.strip()))
    except (ValueError, AttributeError):
        return None


def write_staging_blob(staging_id: str, safe_filename: str, content: bytes) -> Path:
    """写入暂存目录 ``uploads/staging/{uuid}/{safe_filename}``。"""
    sid = _parse_staging_id(staging_id)
    if not sid:
        raise ValueError("invalid staging_id")
    d = STAGING_PARENT / sid
    d.mkdir(parents=True, exist_ok=True)
    out = d / safe_filename
    out.write_bytes(content)
    return out


def resolve_staging_file(staging_id: str) -> Path | None:
    """返回暂存目录内唯一文件路径；目录不存在或非单文件则 None。"""
    sid = _parse_staging_id(staging_id)
    if not sid:
        return None
    d = STAGING_PARENT / sid
    if not d.is_dir():
        return None
    files = [p for p in d.iterdir() if p.is_file()]
    if len(files) != 1:
        return None
    return files[0]


def remove_staging(staging_id: str) -> None:
    sid = _parse_staging_id(staging_id)
    if not sid:
        return
    target = STAGING_PARENT / sid
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)
