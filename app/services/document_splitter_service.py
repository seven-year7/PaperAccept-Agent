"""
/**
 * @Module: app/services/document_splitter_service.py
 * @Description: 文档分片：Markdown 标题 / 递归字符 / 层级 tiktoken；可选 ##·### 标题 + SemanticChunker + token 硬顶。
 * @Interface: DocumentSplitterService.split_document
 */
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, cast

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from loguru import logger

from app.config import config


class DocumentSplitterService:
    """文档分割服务 - 使用 LangChain 的分割器"""

    def __init__(self):
        """初始化文档分割服务"""
        self.chunk_size = config.chunk_max_size
        self.chunk_overlap = config.chunk_overlap

        # Markdown 标题分割器 (只按一级和二级标题分割，减少分片数)
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                # 不再按三级标题分割，避免过度碎片化
            ],
            strip_headers=False,
        )

        # 语义 Markdown：按 # / ## / ### 粗分章节（报告常见结构）
        self.markdown_semantic_header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=[
                ("#", "h1"),
                ("##", "h2"),
                ("###", "h3"),
            ],
            strip_headers=False,
        )

        # 递归字符分割器 (用于二次分割，使用更大的chunk_size)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size * 2,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

        self._cached_semantic_chunker: Optional[Any] = None

        logger.info(
            f"文档分割服务初始化完成, chunk_size={self.chunk_size}, "
            f"secondary_chunk_size={self.chunk_size * 2}, "
            f"overlap={self.chunk_overlap}, "
            f"hierarchical_token_chunks={config.rag_hierarchical_chunks_enabled}, "
            f"semantic_md={config.rag_markdown_semantic_chunk_enabled}"
        )

    def _semantic_breakpoint_type(self) -> Literal["percentile", "standard_deviation", "interquartile", "gradient"]:
        allowed = frozenset({"percentile", "standard_deviation", "interquartile", "gradient"})
        raw = (config.rag_semantic_breakpoint_type or "percentile").strip().lower()
        if raw not in allowed:
            logger.warning(
                f"[WARN][Embedding]: 非法 rag_semantic_breakpoint_type={raw!r}，回退 percentile"
            )
            return "percentile"
        return cast(
            Literal["percentile", "standard_deviation", "interquartile", "gradient"],
            raw,
        )

    def _get_semantic_chunker(self) -> Any:
        if self._cached_semantic_chunker is None:
            # @Step: 延迟导入 — 避免在未安装 langchain-experimental 时模块级导入失败
            from langchain_experimental.text_splitter import SemanticChunker

            from app.services.vector_embedding_service import vector_embedding_service

            self._cached_semantic_chunker = SemanticChunker(
                embeddings=vector_embedding_service,
                breakpoint_threshold_type=self._semantic_breakpoint_type(),
                breakpoint_threshold_amount=float(config.rag_semantic_breakpoint_amount),
                buffer_size=max(1, int(config.rag_semantic_buffer_size)),
            )
            logger.info(
                "[INFO][Embedding]: SemanticChunker 已构造 "
                f"type={config.rag_semantic_breakpoint_type} amount={config.rag_semantic_breakpoint_amount} "
                f"buffer_size={config.rag_semantic_buffer_size}"
            )
        return self._cached_semantic_chunker

    def _tiktoken_length(self, text: str) -> int:
        try:
            import tiktoken
        except ImportError as e:
            raise RuntimeError("语义分块 token 保底需要 tiktoken：pip install tiktoken") from e
        enc = tiktoken.get_encoding(config.rag_tokenizer_encoding)
        return len(enc.encode(text or ""))

    def _enforce_max_tokens_per_chunk(self, documents: List[Document]) -> List[Document]:
        """语义切块后单块 token 超过 rag_semantic_max_chunk_tokens 时二次切分。"""
        max_tok = max(64, int(config.rag_semantic_max_chunk_tokens))
        overlap = max(0, min(int(config.rag_semantic_chunk_overlap_tokens), max_tok // 2))

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tok,
            chunk_overlap=overlap,
            length_function=self._tiktoken_length,
            separators=["\n\n", "\n", "。", "；", " ", ""],
        )
        out: List[Document] = []
        extra_split_count = 0
        for doc in documents:
            if self._tiktoken_length(doc.page_content) <= max_tok:
                out.append(doc)
                continue
            subdocs = splitter.split_documents([doc])
            extra_split_count += max(0, len(subdocs) - 1)
            for j, sd in enumerate(subdocs):
                meta = dict(sd.metadata or {})
                meta["semantic_oversize_split"] = True
                meta["semantic_oversize_part_index"] = j
                meta["semantic_oversize_part_total"] = len(subdocs)
                sd.metadata = meta
                out.append(sd)
        if extra_split_count:
            logger.info(
                f"[INFO][Embedding]: token 硬顶二次切分 extra_chunks={extra_split_count} max_tok={max_tok}"
            )
        return out

    def _hierarchical_token_chunks(self, text: str, base_metadata: Dict[str, Any]) -> List[Document]:
        """
        父级 token 滑窗后再子级 token 滑窗；page_content 为子文本，metadata 含 parent_id、parent_text。
        """
        try:
            import tiktoken
        except ImportError as e:
            raise RuntimeError(
                "层级分块需要安装 tiktoken：pip install tiktoken"
            ) from e

        enc = tiktoken.get_encoding(config.rag_tokenizer_encoding)

        def tok_len(s: str) -> int:
            return len(enc.encode(s))

        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(1, int(config.rag_parent_chunk_tokens)),
            chunk_overlap=max(0, int(config.rag_parent_chunk_overlap_tokens)),
            length_function=tok_len,
            separators=["\n\n", "\n", "。", "；", " ", ""],
        )
        child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max(1, int(config.rag_child_chunk_tokens)),
            chunk_overlap=max(0, int(config.rag_child_chunk_overlap_tokens)),
            length_function=tok_len,
            separators=["\n\n", "\n", "。", "；", " ", ""],
        )
        out: List[Document] = []
        for parent_text in parent_splitter.split_text(text):
            pt = parent_text.strip()
            if not pt:
                continue
            parent_id = str(uuid.uuid4())
            child_idx = 0
            for child_text in child_splitter.split_text(pt):
                ct = child_text.strip()
                if not ct:
                    continue
                meta = {
                    **base_metadata,
                    "parent_id": parent_id,
                    "parent_text": pt,
                    "child_index": child_idx,
                }
                out.append(Document(page_content=ct, metadata=meta))
                child_idx += 1
        return out

    def split_markdown_semantic(self, content: str, file_path: str = "") -> List[Document]:
        """Markdown：# / ## / ### 粗分后，每节内 SemanticChunker，再 token 硬顶。"""
        if not content or not content.strip():
            logger.warning(f"Markdown 文档内容为空: {file_path}")
            return []

        if config.rag_hierarchical_chunks_enabled:
            logger.warning(
                "[WARN][Embedding]: rag_hierarchical_chunks_enabled 与 semantic_md 同时开启，本路径优先语义 Markdown"
            )

        md_sections = self.markdown_semantic_header_splitter.split_text(content)
        semantic_chunker = self._get_semantic_chunker()
        all_out: List[Document] = []
        section_ordinal = 0

        for sec_doc in md_sections:
            text = (sec_doc.page_content or "").strip()
            if not text:
                continue
            base: Dict[str, Any] = {
                "_source": file_path,
                "_extension": ".md",
                "_file_name": Path(file_path).name,
                "markdown_semantic_section_index": section_ordinal,
            }
            for k, v in (sec_doc.metadata or {}).items():
                if k not in base and isinstance(v, (str, int, float, bool, type(None))):
                    base[k] = v

            section_doc = Document(page_content=text, metadata=dict(base))
            try:
                chunks = semantic_chunker.split_documents([section_doc])
            except Exception as e:
                logger.error(f"[ERROR][Embedding]: SemanticChunker 失败 path={file_path} section={section_ordinal} err={e}")
                raise

            for c in chunks:
                merged = dict(base)
                for k, v in (c.metadata or {}).items():
                    if isinstance(v, (str, int, float, bool, type(None))):
                        merged[k] = v
                c.metadata = merged
                all_out.append(c)

            section_ordinal += 1

        final_docs = self._enforce_max_tokens_per_chunk(all_out)
        logger.info(
            f"[INFO][Embedding]: Markdown 语义分割完成 path={file_path} sections={section_ordinal} "
            f"chunks_before_cap={len(all_out)} chunks_after_cap={len(final_docs)}"
        )
        return final_docs

    def split_markdown_hierarchical(self, content: str, file_path: str = "") -> List[Document]:
        """Markdown：标题粗分后，每节内父/子 token 层级切分。"""
        if not content or not content.strip():
            logger.warning(f"Markdown 文档内容为空: {file_path}")
            return []
        md_docs = self.markdown_splitter.split_text(content)
        all_out: List[Document] = []
        for doc in md_docs:
            base: Dict[str, Any] = {
                "_source": file_path,
                "_extension": ".md",
                "_file_name": Path(file_path).name,
            }
            for k, v in (doc.metadata or {}).items():
                if k not in base and isinstance(v, (str, int, float, bool, type(None))):
                    base[k] = v
            all_out.extend(self._hierarchical_token_chunks(doc.page_content, base))
        logger.info(f"Markdown 层级分割完成: {file_path} -> {len(all_out)} 个子块")
        return all_out

    def split_text_hierarchical(self, content: str, file_path: str = "") -> List[Document]:
        """纯文本：整篇父/子 token 层级切分。"""
        if not content or not content.strip():
            logger.warning(f"文本文档内容为空: {file_path}")
            return []
        base = {
            "_source": file_path,
            "_extension": Path(file_path).suffix,
            "_file_name": Path(file_path).name,
        }
        out = self._hierarchical_token_chunks(content, base)
        logger.info(f"文本层级分割完成: {file_path} -> {len(out)} 个子块")
        return out

    def split_markdown(self, content: str, file_path: str = "") -> List[Document]:
        """
        分割 Markdown 文档 (两阶段分割 + 合并小片段)
        """
        if not content or not content.strip():
            logger.warning(f"Markdown 文档内容为空: {file_path}")
            return []

        try:
            md_docs = self.markdown_splitter.split_text(content)
            docs_after_split = self.text_splitter.split_documents(md_docs)
            final_docs = self._merge_small_chunks(docs_after_split, min_size=300)

            for doc in final_docs:
                doc.metadata["_source"] = file_path
                doc.metadata["_extension"] = ".md"
                doc.metadata["_file_name"] = Path(file_path).name

            logger.info(f"Markdown 分割完成: {file_path} -> {len(final_docs)} 个分片")
            return final_docs

        except Exception as e:
            logger.error(f"Markdown 分割失败: {file_path}, 错误: {e}")
            raise

    def split_text(self, content: str, file_path: str = "") -> List[Document]:
        if not content or not content.strip():
            logger.warning(f"文本文档内容为空: {file_path}")
            return []

        try:
            docs = self.text_splitter.create_documents(
                texts=[content],
                metadatas=[
                    {
                        "_source": file_path,
                        "_extension": Path(file_path).suffix,
                        "_file_name": Path(file_path).name,
                    }
                ],
            )

            logger.info(f"文本分割完成: {file_path} -> {len(docs)} 个分片")
            return docs

        except Exception as e:
            logger.error(f"文本分割失败: {file_path}, 错误: {e}")
            raise

    def split_document(self, content: str, file_path: str = "") -> List[Document]:
        if config.rag_markdown_semantic_chunk_enabled and file_path.endswith(".md"):
            return self.split_markdown_semantic(content, file_path)
        if config.rag_hierarchical_chunks_enabled:
            if file_path.endswith(".md"):
                return self.split_markdown_hierarchical(content, file_path)
            return self.split_text_hierarchical(content, file_path)
        if file_path.endswith(".md"):
            return self.split_markdown(content, file_path)
        return self.split_text(content, file_path)

    def _merge_small_chunks(
        self, documents: List[Document], min_size: int = 300
    ) -> List[Document]:
        if not documents:
            return []

        merged_docs = []
        current_doc = None

        for doc in documents:
            doc_size = len(doc.page_content)

            if current_doc is None:
                current_doc = doc
            elif doc_size < min_size and len(current_doc.page_content) < self.chunk_size * 2:
                current_doc.page_content += "\n\n" + doc.page_content
            else:
                merged_docs.append(current_doc)
                current_doc = doc

        if current_doc is not None:
            merged_docs.append(current_doc)

        return merged_docs


document_splitter_service = DocumentSplitterService()
