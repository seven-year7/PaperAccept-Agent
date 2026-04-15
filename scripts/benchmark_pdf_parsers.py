"""
/**
 * @Module: scripts/benchmark_pdf_parsers.py
 * @Description: 对 docx/ 下 PDF 做 Docling vs pypdf A/B，导出 Markdown 到 docs/ 并记录耗时。
 * @Interface: python scripts/benchmark_pdf_parsers.py [--input-dir docx] [--output-dir docs/pdf_ab]
 */
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from docling.document_converter import DocumentConverter  # noqa: E402


@dataclass
class ParseResult:
    method: str
    ok: bool
    elapsed_ms: int
    output_chars: int
    output_path: str
    error: str = ""


def _sanitize_name(name: str) -> str:
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, "_")
    return name


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_timed(
    method: str,
    fn: Callable[[Path], str],
    pdf_path: Path,
    out_path: Path,
) -> ParseResult:
    start = time.perf_counter()
    try:
        content = fn(pdf_path)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        _write_text(out_path, content)
        return ParseResult(
            method=method,
            ok=True,
            elapsed_ms=elapsed_ms,
            output_chars=len(content),
            output_path=str(out_path.as_posix()),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return ParseResult(
            method=method,
            ok=False,
            elapsed_ms=elapsed_ms,
            output_chars=0,
            output_path=str(out_path.as_posix()),
            error=str(exc),
        )


def _docling_to_markdown(converter: DocumentConverter, pdf_path: Path) -> str:
    conv = converter.convert(str(pdf_path))
    return conv.document.export_to_markdown()


def _pypdf_to_markdown(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append((page.extract_text() or "").strip())
    text = "\n\n".join([p for p in pages if p]).strip()
    # 统一输出 markdown 文件，便于肉眼对比
    return text


def _build_md_summary(rows: list[dict[str, str]]) -> str:
    header = (
        "# PDF 解析 A/B 测试报告\n\n"
        "| file | method | ok | elapsed_ms | output_chars | output_path | error |\n"
        "|---|---|---:|---:|---:|---|---|\n"
    )
    lines: list[str] = []
    for r in rows:
        lines.append(
            f"| {r['file']} | {r['method']} | {r['ok']} | {r['elapsed_ms']} | "
            f"{r['output_chars']} | {r['output_path']} | {r['error']} |"
        )
    return header + "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 解析 A/B（Docling vs pypdf）")
    parser.add_argument("--input-dir", default="docx", help="PDF 输入目录")
    parser.add_argument("--output-dir", default="docs/pdf_ab", help="输出目录（md/csv）")
    args = parser.parse_args()

    input_dir = (_ROOT / args.input_dir).resolve()
    output_dir = (_ROOT / args.output_dir).resolve()
    if not input_dir.exists():
        print(f"[ERROR] 输入目录不存在: {input_dir}", file=sys.stderr)
        return 1

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"[ERROR] 未找到 PDF: {input_dir}", file=sys.stderr)
        return 1

    converter = DocumentConverter()
    pypdf_available = True
    try:
        import pypdf  # noqa: F401
    except Exception:
        pypdf_available = False

    rows: list[dict[str, str]] = []
    print(f"[INFO] 输入目录: {input_dir}")
    print(f"[INFO] 输出目录: {output_dir}")
    print(f"[INFO] PDF 数量: {len(pdf_files)}")
    print(f"[INFO] pypdf 可用: {pypdf_available}")

    for pdf_path in pdf_files:
        safe_stem = _sanitize_name(pdf_path.stem)
        print(f"\n[INFO] 测试文件: {pdf_path.name}")

        docling_out = output_dir / "docling" / f"{safe_stem}.md"
        docling_result = _run_timed(
            "docling",
            lambda p: _docling_to_markdown(converter, p),
            pdf_path,
            docling_out,
        )
        print(
            f"  - docling: ok={docling_result.ok} elapsed_ms={docling_result.elapsed_ms} "
            f"chars={docling_result.output_chars}"
        )
        rows.append(
            {
                "file": pdf_path.name,
                "method": docling_result.method,
                "ok": str(docling_result.ok),
                "elapsed_ms": str(docling_result.elapsed_ms),
                "output_chars": str(docling_result.output_chars),
                "output_path": docling_result.output_path,
                "error": docling_result.error.replace("\n", " "),
            }
        )

        pypdf_out = output_dir / "pypdf" / f"{safe_stem}.md"
        if pypdf_available:
            pypdf_result = _run_timed("pypdf", _pypdf_to_markdown, pdf_path, pypdf_out)
        else:
            pypdf_result = ParseResult(
                method="pypdf",
                ok=False,
                elapsed_ms=0,
                output_chars=0,
                output_path=str(pypdf_out.as_posix()),
                error="pypdf 未安装，已跳过",
            )
        print(
            f"  - pypdf: ok={pypdf_result.ok} elapsed_ms={pypdf_result.elapsed_ms} "
            f"chars={pypdf_result.output_chars}"
        )
        rows.append(
            {
                "file": pdf_path.name,
                "method": pypdf_result.method,
                "ok": str(pypdf_result.ok),
                "elapsed_ms": str(pypdf_result.elapsed_ms),
                "output_chars": str(pypdf_result.output_chars),
                "output_path": pypdf_result.output_path,
                "error": pypdf_result.error.replace("\n", " "),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file", "method", "ok", "elapsed_ms", "output_chars", "output_path", "error"],
        )
        writer.writeheader()
        writer.writerows(rows)

    md_path = output_dir / "summary.md"
    _write_text(md_path, _build_md_summary(rows))

    print(f"\n[OK] 汇总 CSV: {csv_path.as_posix()}")
    print(f"[OK] 汇总 MD : {md_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
