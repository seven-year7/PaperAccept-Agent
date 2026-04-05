"""
/**
 * @Module: app/services/long_term_memory_store.py
 * @Description: 全局双 Markdown 长期记忆（Agent.md / Memory.md），统一落在 long_term_memory_base_path 根目录；agent_rules→Agent.md，user_profile→Memory.md；meta 条目中可记录 user_id 供审计。
 * @Interface: sanitize_user_id_for_path / read_agent_rules_markdown / read_user_profile_markdown / append_memory_entry / build_injection_blocks
 */
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from loguru import logger

from app.config import config

_ALLOWED_USER_ID_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
)

MemoryKind = Literal["user_profile", "agent_rules"]
MemorySource = Literal["explicit", "inferred"]

_FILE_LOCKS: Dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    # @Step: 1 - 同进程内对同一文件串行化追加，降低并发写损坏概率
    with _FILE_LOCKS_GUARD:
        if path not in _FILE_LOCKS:
            _FILE_LOCKS[path] = threading.Lock()
        return _FILE_LOCKS[path]


def sanitize_user_id_for_path(user_id: str) -> str:
    """
    将 user_id 转为安全的单路径名片段；禁止路径穿越与非常规字符。
    长期记忆已改为全局双文件，本函数保留供其它模块或审计字段使用。
    # @Security: 非白名单字符统一哈希，避免 ../ 等注入。
    """
    uid = (user_id or "").strip() or "default"
    if len(uid) <= 128 and all(c in _ALLOWED_USER_ID_CHARS for c in uid):
        return uid
    digest = hashlib.sha256(uid.encode("utf-8")).hexdigest()
    logger.info(f"[INFO][LTM]: user_id 已哈希为安全片段 raw_len={len(uid)}")
    return digest


def _resolve_base_dir() -> Path:
    raw = Path(config.long_term_memory_base_path)
    return raw if raw.is_absolute() else Path.cwd() / raw


def _paths_global() -> tuple[Path, Path, Path]:
    """全局唯一路径：base/Agent.md（助手规范）、base/Memory.md（用户侧记忆）、base/memory_meta.json。"""
    base = _resolve_base_dir()
    return (
        base / "Agent.md",
        base / "Memory.md",
        base / "memory_meta.json",
    )


def long_term_memory_config_snapshot() -> Dict[str, Any]:
    """
    启动或排障用：当前生效的长期记忆开关与绝对路径（便于对照「为何没写入」）。
    # @Agent_Logic: 写入只会在模型调用 append_long_term_memory 且 write_enabled=true 时发生。
    """
    base = _resolve_base_dir()
    agent_p, memory_p, meta_p = _paths_global()
    reg = bool(config.long_term_memory_enabled and config.long_term_memory_write_enabled)
    return {
        "read_enabled": config.long_term_memory_enabled,
        "write_enabled": config.long_term_memory_write_enabled,
        "append_tool_registered": reg,
        "env_file_hint": "LONG_TERM_MEMORY_WRITE_ENABLED / LONG_TERM_MEMORY_ENABLED",
        "base_dir": str(base.resolve()),
        "agent_md": str(agent_p.resolve()),
        "memory_md": str(memory_p.resolve()),
        "memory_meta": str(meta_p.resolve()),
    }


def _truncate_for_injection(text: str, label: str) -> str:
    max_chars = int(config.long_term_memory_max_chars_per_file)
    if len(text) <= max_chars:
        return text
    logger.warning(
        f"[WARN][LTM]: 注入前截断 {label} len={len(text)} max={max_chars}"
    )
    return text[:max_chars] + "\n\n…（已截断，见 long_term_memory_max_chars_per_file）"


def read_agent_rules_markdown(user_id: str) -> str:
    """读取助手行为规范 MD；不存在或为空返回空串。（user_id 保留参数以兼容调用方，路径与 user 无关）"""
    if not config.long_term_memory_enabled:
        return ""
    path = _paths_global()[0]
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error(f"[ERROR][LTM]: 读取 agent_rules 失败 path={path} err={e}")
        return ""


def read_user_profile_markdown(user_id: str) -> str:
    """读取用户画像 MD；不存在或为空返回空串。（user_id 保留参数以兼容调用方，路径与 user 无关）"""
    if not config.long_term_memory_enabled:
        return ""
    path = _paths_global()[1]
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as e:
        logger.error(f"[ERROR][LTM]: 读取 user_profile 失败 path={path} err={e}")
        return ""


def _load_meta(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"entries": []}
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("entries"), list):
            return parsed
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[WARN][LTM]: meta 解析失败将重建 path={path} err={e}")
    return {"entries": []}


def _save_meta(path: Path, meta: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def append_memory_entry(
    user_id: str,
    memory_kind: MemoryKind,
    content: str,
    *,
    source: MemorySource = "explicit",
    confidence: float = 1.0,
) -> str:
    """
    追加一条长期记忆到全局对应 Markdown，并写入 meta 条目（含 request user_id 审计；预留 source/confidence）。
    首版仅允许 source=explicit。
    """
    # @Step: 2 - 首版拒绝 inferred，避免静默误写入
    if source != "explicit":
        logger.warning(f"[WARN][LTM]: 拒绝非 explicit 写入 source={source}")
        return "[LTM] 拒绝写入：当前仅支持 source=explicit（推断写入未启用）。"

    if not config.long_term_memory_enabled:
        return "[LTM] 长期记忆读取已关闭（long_term_memory_enabled=false），未写入。"

    if not config.long_term_memory_write_enabled:
        return (
            "[LTM] 写入开关为 false（long_term_memory_write_enabled）："
            "配置未允许落盘，未写入 Agent.md / Memory.md。"
        )

    text = (content or "").strip()
    if not text:
        return "[LTM] 内容为空，未写入。"

    uid = (user_id or "").strip() or "default"
    agent_path, profile_path, meta_path = _paths_global()
    md_path = profile_path if memory_kind == "user_profile" else agent_path

    lock = _lock_for(str(md_path.resolve()))
    with lock:
        try:
            md_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"[ERROR][LTM]: 无法创建目录 parent={md_path.parent} err={e}")
            return f"[LTM] 写入失败：无法创建目录（权限或路径问题）：{e}"

        existing = ""
        if md_path.is_file():
            try:
                existing = md_path.read_text(encoding="utf-8")
            except OSError as e:
                logger.error(f"[ERROR][LTM]: 读取待追加文件失败 path={md_path} err={e}")
                return f"[LTM] 写入失败：无法读取现有文件（权限或占用）：{e}"

        max_chars = int(config.long_term_memory_max_chars_per_file)
        block = (
            f"\n\n---\n"
            f"<!-- ltm: kind={memory_kind} source={source} "
            f"confidence={confidence} ts={datetime.now(timezone.utc).isoformat()} -->\n"
            f"{text}\n"
        )
        new_body = (existing.rstrip() + block) if existing.strip() else text
        if len(new_body) > max_chars:
            logger.warning(
                f"[WARN][LTM]: 追加后超长，从头部截断 len={len(new_body)} max={max_chars}"
            )
            new_body = new_body[-max_chars:]

        try:
            md_path.write_text(new_body.strip() + "\n", encoding="utf-8")
        except OSError as e:
            logger.error(f"[ERROR][LTM]: 写入 Markdown 失败 path={md_path} err={e}")
            return f"[LTM] 写入失败：无写权限或磁盘错误（{e}）。请检查进程对目录的权限。"

        meta = _load_meta(meta_path)
        entries: List[Dict[str, Any]] = list(meta.get("entries") or [])
        preview = text.replace("\n", " ")[:120]
        entries.append(
            {
                "memory_kind": memory_kind,
                "source": source,
                "confidence": float(confidence),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "preview": preview,
                "user_id": uid,
            }
        )
        meta["entries"] = entries[-500:]
        try:
            _save_meta(meta_path, meta)
        except OSError as e:
            logger.error(f"[ERROR][LTM]: 写入 memory_meta 失败 path={meta_path} err={e}")
            return (
                f"[LTM] 正文已写入 {md_path.name}，但 memory_meta.json 保存失败：{e}。"
                "请检查同目录写权限。"
            )

    logger.info(
        f"[INFO][LTM]: 已追加 memory_kind={memory_kind} request_user_id={uid} path={md_path}"
    )
    return f"[LTM] 已写入 {memory_kind} → {md_path.name}（{len(text)} 字符）。"


def build_injection_blocks(user_id: str) -> List[tuple[str, str]]:
    """
    返回 [(label, body), ...] 供 RagAgentService 注入 SystemMessage。
    仅包含非空正文；body 已做长度截断。内容与 user_id 无关，均来自全局双 MD。
    """
    if not config.long_term_memory_enabled:
        return []

    blocks: List[tuple[str, str]] = []

    agent_rules = read_agent_rules_markdown("")
    if agent_rules:
        blocks.append(
            (
                "LONG_TERM_AGENT_RULES",
                _truncate_for_injection(agent_rules, "agent_rules"),
            )
        )

    profile = read_user_profile_markdown("")
    if profile:
        blocks.append(
            (
                "LONG_TERM_USER_PROFILE",
                _truncate_for_injection(profile, "user_profile"),
            )
        )

    return blocks
