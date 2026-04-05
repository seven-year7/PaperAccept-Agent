"""
/**
 * @Module: app/agent/paper/reading_sanitize.py
 * @Description: 阅读节点用文本清洗（换行、空白、控制字符），供单篇字段与合并前块整理复用。
 * @Interface: sanitize_reading_paragraph / format_reading_title_line / merge_reading_markdown_blocks
 */
"""

from __future__ import annotations

import re

# @Step: 1 - 标题行过长时截断，避免 Markdown 行过长或目录异常
_MAX_TITLE_DISPLAY_LEN = 240


def sanitize_reading_paragraph(text: str) -> str:
    """统一换行、去控制字符、压缩多余空行。"""
    # @Agent_Logic: LLM 与 arXiv 摘要可能含 \\r 与连续空行，合并进 md 前收敛为可读段落
    if not text:
        return ""
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    buf: list[str] = []
    for ch in s:
        o = ord(ch)
        if ch == "\n":
            buf.append(ch)
        elif ch == "\t":
            buf.append(" ")
        elif o >= 32 and o != 127:
            buf.append(ch)
    s = "".join(buf)
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    s = s.strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


def format_reading_title_line(title: str) -> str:
    """单行展示用标题：压空白，必要时截断。"""
    t = re.sub(r"\s+", " ", (title or "").strip())
    if len(t) > _MAX_TITLE_DISPLAY_LEN:
        t = t[: _MAX_TITLE_DISPLAY_LEN - 1].rstrip() + "…"
    return t or "（无标题）"


def merge_reading_markdown_blocks(blocks: list[str], document_heading: str = "# 论文阅读摘要") -> str:
    """块级 strip、统一分隔，全文首尾整洁。"""
    cleaned = [b.strip() for b in blocks if b and b.strip()]
    body = "\n\n".join(cleaned)
    out = f"{document_heading}\n\n{body}\n" if body else f"{document_heading}\n\n（无有效阅读块）\n"
    return out.strip() + "\n"
