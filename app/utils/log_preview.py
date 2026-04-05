"""
/**
 * @Module: app/utils/log_preview.py
 * @Description: 日志用正文单行摘要（换行压平、截断），避免多行日志污染。
 * @Interface: preview_for_log
 */
"""


def preview_for_log(text: str, max_chars: int = 240) -> str:
    t = (text or "").replace("\r", " ").replace("\n", " ").strip()
    if len(t) > max_chars:
        return t[: max_chars - 1] + "…"
    return t
