"""
/**
 * @Module: scripts/dump_rag_recall.py
 * @Description: 对给定 query 走与对话相同的 RAG 召回路径，将每条命中的**完整正文**写入 Markdown（真实数据，非示例模板）。
 * @Interface: python scripts/dump_rag_recall.py "你的问题" [--tenant-id default] [--out docx/my_recall.md]
 */
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="从项目根 .env 加载配置，执行 RAG 召回并输出每条 chunk 的全文到 Markdown。"
    )
    parser.add_argument("query", help="检索用的 query 文本")
    parser.add_argument(
        "--tenant-id",
        default="default",
        help="与对话 TenantId 一致；RAG_TENANT_ISOLATION_ENABLED=true 时用于 Milvus 过滤",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="写入的 .md 路径（默认打印到 stdout）",
    )
    args = parser.parse_args()

    from app.config import config
    from app.core.milvus_client import milvus_manager
    from app.tools.knowledge_tool import _retrieve_core, format_docs
    from app.utils.rag_recall_dump import format_bm25_section_lines

    q = (args.query or "").strip()
    if not q:
        print("query 不能为空", file=sys.stderr)
        return 2

    try:
        try:
            milvus_manager.connect()
        except Exception as e:
            print(
                f"[ERROR] 无法连接 Milvus（与 uvicorn 启动时相同依赖）。请确认 Milvus 已起且 .env 中 "
                f"MILVUS_HOST/MILVUS_PORT 正确。\n详情: {e}",
                file=sys.stderr,
            )
            return 1

        try:
            core = _retrieve_core(q, tenant_id=str(args.tenant_id or ""))
        except Exception as e:
            print(f"[ERROR] 召回执行失败: {e}", file=sys.stderr)
            return 1

        docs = core["docs"]
        bm25_candidates = list(core.get("bm25_candidates") or [])
        ho = core.get("hybrid_obs") or {}
        lines: list[str] = []
        lines.append("# RAG 召回实录（真实运行输出）")
        lines.append("")
        lines.append(f"- **生成时间（UTC）**: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"- **Query**: {q}")
        lines.append(f"- **TenantId**: {args.tenant_id}")
        lines.append(f"- **RAG_HYBRID_ENABLED**: {config.rag_hybrid_enabled}")
        lines.append(f"- **RAG_TOP_K**（纯向量 limit / 混合融合后条数上限）: {config.rag_top_k}")
        lines.append(
            f"- **门控**: below_threshold={core.get('below_threshold')} "
            f"top1_distance={core.get('top1_distance')} chunk_count={core.get('chunk_count')}"
        )
        if ho:
            lines.append(
                f"- **混合观测**: vec_hits={ho.get('vec_hits')} bm25_hits={ho.get('bm25_hits')} "
                f"es_degraded={ho.get('es_degraded')}"
            )
        lines.append("")

        if not docs:
            lines.append("## 结果")
            lines.append("")
            lines.append("**无命中**：`chunk_count=0`，库中未返回任何 chunk。")
            lines.append("")
        else:
            lines.append("## 模型侧格式化预览（与 `format_docs` 一致）")
            lines.append("")
            lines.append("```text")
            lines.append(format_docs(docs))
            lines.append("```")
            lines.append("")
            lines.extend(
                format_bm25_section_lines(
                    bm25_candidates=bm25_candidates,
                    hybrid_obs=ho,
                    title_heading="##",
                )
            )
            lines.append("## 融合后条目（_retrieve_source）")
            lines.append("")
            for i, doc in enumerate(docs, start=1):
                md = dict(doc.metadata or {})
                lines.append(f"## 条目 {i}")
                lines.append("")
                lines.append(f"- **_chunk_id**: {md.get('_chunk_id', '')}")
                lines.append(f"- **_retrieve_source**: {md.get('_retrieve_source', '（未标，多为向量）')}")
                if "_distance" in md:
                    lines.append(f"- **L2 距离**（越小越相似，仅向量路）: {md.get('_distance')}")
                lines.append(f"- **_file_name**: {md.get('_file_name', md.get('file_name', ''))}")
                lines.append(f"- **_source**: {md.get('_source', md.get('source', ''))}")
                rest = {
                    k: v
                    for k, v in md.items()
                    if k
                    not in (
                        "_chunk_id",
                        "_distance",
                        "_retrieve_source",
                        "_file_name",
                        "file_name",
                        "_source",
                        "source",
                        "_degraded",
                        "_fusion_score",
                        "_rrf_score",
                        "_bm25_score",
                    )
                }
                if rest:
                    lines.append(f"- **metadata（节选 JSON）**: `{json.dumps(rest, ensure_ascii=False)[:2000]}`")
                lines.append("")
                lines.append("### 正文（完整 `page_content`）")
                lines.append("")
                lines.append("```")
                lines.append(doc.page_content or "")
                lines.append("```")
                lines.append("")

        text = "\n".join(lines)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
            print(f"[INFO] 已写入 {args.out.resolve()}", file=sys.stderr)
        else:
            print(text)
        return 0
    finally:
        try:
            milvus_manager.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(_main())
