"""
/**
 * @Module: scripts/test_pdf_embed_local.py
 * @Description: 本地直连向量索引服务，验证 docx/test.pdf 能否完成 PDF 文本提取与嵌入写入。
 * @Interface: python scripts/test_pdf_embed_local.py [--file docx/test.pdf] [--tenant test_pdf]
 */
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.vector_index_service import vector_index_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 PDF 本地嵌入（直连 VectorIndexService）")
    parser.add_argument(
        "--file",
        default="docx/test.pdf",
        help="待测试的 PDF 文件路径（默认: docx/test.pdf）",
    )
    parser.add_argument(
        "--tenant",
        default="test_pdf",
        help="测试写入使用的 tenant_id（默认: test_pdf）",
    )
    args = parser.parse_args()

    pdf_path = Path(args.file).resolve()
    if not pdf_path.exists():
        print(f"[ERROR][PdfEmbedSmoke]: 文件不存在: {pdf_path}", file=sys.stderr)
        return 1
    if pdf_path.suffix.lower() != ".pdf":
        print(f"[ERROR][PdfEmbedSmoke]: 仅支持 .pdf，当前: {pdf_path.name}", file=sys.stderr)
        return 1

    # @Step: 1 - 触发 PDF 抽取 + 分块 + 向量写入主链路
    # @Agent_Logic: 复用生产代码路径，避免脚本与主逻辑分叉导致“测得过、线上不过”
    # @Security: 仅打印统计信息，不输出原始 PDF 正文
    try:
        chunk_count = vector_index_service.index_single_file(
            str(pdf_path),
            tenant_id=args.tenant,
        )
    except Exception as exc:
        print(f"[ERROR][PdfEmbedSmoke]: 嵌入失败 err={exc}", file=sys.stderr)
        return 1

    print(
        "[OK][PdfEmbedSmoke]: "
        f"file={pdf_path.as_posix()} tenant={args.tenant} chunk_count={chunk_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
