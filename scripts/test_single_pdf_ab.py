"""
/**
 * @Module: scripts/test_single_pdf_ab.py
 * @Description: 仅针对单个 PDF（默认 docx/test.pdf）执行 Docling vs pypdf A/B 测试并记录耗时。
 * @Interface: python scripts/test_single_pdf_ab.py [--file docx/test.pdf] [--out-dir docs/test_pdf_ab]
 */
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from docling.document_converter import DocumentConverter


def _write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_docling(pdf_path: Path, out_path: Path) -> dict:
    started = time.perf_counter()
    try:
        converter = DocumentConverter()
        result = converter.convert(str(pdf_path))
        text = result.document.export_to_markdown()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _write_utf8(out_path, text)
        return {
            "method": "docling",
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "chars": len(text),
            "output_path": out_path.as_posix(),
            "error": "",
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "method": "docling",
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "chars": 0,
            "output_path": out_path.as_posix(),
            "error": str(exc),
        }


def _run_pypdf(pdf_path: Path, out_path: Path) -> dict:
    started = time.perf_counter()
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        chunks: list[str] = []
        for page in reader.pages:
            piece = (page.extract_text() or "").strip()
            if piece:
                chunks.append(piece)
        text = "\n\n".join(chunks).strip()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        _write_utf8(out_path, text)
        return {
            "method": "pypdf",
            "ok": True,
            "elapsed_ms": elapsed_ms,
            "chars": len(text),
            "output_path": out_path.as_posix(),
            "error": "",
        }
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "method": "pypdf",
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "chars": 0,
            "output_path": out_path.as_posix(),
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="单个 PDF A/B 测试（Docling vs pypdf）")
    parser.add_argument("--file", default="docx/test.pdf", help="目标 PDF 路径")
    parser.add_argument("--out-dir", default="docs/test_pdf_ab", help="输出目录")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    pdf_path = (root / args.file).resolve()
    out_dir = (root / args.out_dir).resolve()

    if not pdf_path.exists():
        print(f"[ERROR] 文件不存在: {pdf_path}", file=sys.stderr)
        return 1
    if pdf_path.suffix.lower() != ".pdf":
        print(f"[ERROR] 仅支持 PDF: {pdf_path.name}", file=sys.stderr)
        return 1

    docling_md = out_dir / "docling_test.md"
    pypdf_md = out_dir / "pypdf_test.md"

    print(f"[INFO] 测试文件: {pdf_path.as_posix()}")
    docling_result = _run_docling(pdf_path, docling_md)
    pypdf_result = _run_pypdf(pdf_path, pypdf_md)

    summary = {
        "file": pdf_path.as_posix(),
        "results": [docling_result, pypdf_result],
    }

    summary_path = out_dir / "summary.json"
    _write_utf8(summary_path, json.dumps(summary, ensure_ascii=False, indent=2))

    print(
        f"[RESULT] docling ok={docling_result['ok']} elapsed_ms={docling_result['elapsed_ms']} "
        f"chars={docling_result['chars']} out={docling_result['output_path']}"
    )
    print(
        f"[RESULT] pypdf   ok={pypdf_result['ok']} elapsed_ms={pypdf_result['elapsed_ms']} "
        f"chars={pypdf_result['chars']} out={pypdf_result['output_path']}"
    )
    print(f"[RESULT] summary -> {summary_path.as_posix()}")

    if docling_result["ok"] or pypdf_result["ok"]:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
