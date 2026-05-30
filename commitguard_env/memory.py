"""Memory management for CommitGuard v2 — chunking, embeddings, and cross-file context.

This module handles repos that exceed the model context window by:
1. Splitting files into overlapping token chunks
2. Embedding chunks with sentence-transformers
3. Retrieving semantically relevant context across files
4. Building import/include graphs for dependency-aware retrieval
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import numpy as np

from .models import CodeChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. CodeChunker — split files into overlapping token windows
# ---------------------------------------------------------------------------

# Default chunk configuration
_DEFAULT_CHUNK_TOKENS: int = 512
_DEFAULT_STRIDE_TOKENS: int = 64


class CodeChunker:
    """Split source files into overlapping token-level chunks.

    Uses a simple whitespace tokeniser for speed.  For accurate sub-word
    counts that match the model, pass a HuggingFace ``tokenizer`` object.
    """

    def __init__(
        self,
        chunk_tokens: int = _DEFAULT_CHUNK_TOKENS,
        stride_tokens: int = _DEFAULT_STRIDE_TOKENS,
        tokenizer: object | None = None,
    ) -> None:
        self._chunk_tokens = chunk_tokens
        self._stride_tokens = stride_tokens
        self._tokenizer = tokenizer

    # -- internal token helpers --

    def _tokenize(self, text: str) -> list[str]:
        if self._tokenizer is not None and hasattr(self._tokenizer, "tokenize"):
            return self._tokenizer.tokenize(text)  # type: ignore[union-attr]
        # Fallback: whitespace split (fast, approximate)
        return text.split()

    def _count_tokens(self, text: str) -> int:
        return len(self._tokenize(text))

    # -- public API --

    def chunk_file(self, file_path: str, content: str) -> list[CodeChunk]:
        """Split *content* into overlapping chunks, tagging each with *file_path*."""
        lines = content.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        start_line = 0
        step = max(1, self._chunk_tokens - self._stride_tokens)

        while start_line < len(lines):
            # Grow the window until we hit the token budget
            end_line = start_line
            token_count = 0
            while end_line < len(lines):
                line_tokens = self._count_tokens(lines[end_line])
                if token_count + line_tokens > self._chunk_tokens and end_line > start_line:
                    break
                token_count += line_tokens
                end_line += 1

            chunk_content = "\n".join(lines[start_line:end_line])
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    start_line=start_line + 1,   # 1-indexed
                    end_line=end_line,            # inclusive
                    content=chunk_content,
                    token_count=token_count,
                )
            )

            # Advance by step (overlap = stride)
            advance = max(1, end_line - start_line - (self._stride_tokens // max(1, token_count // max(1, end_line - start_line))))
            # Simpler: advance by line-count equivalent of step tokens
            advance = max(1, (end_line - start_line) * step // max(1, self._chunk_tokens))
            start_line += advance

            # Guard against infinite loop
            if start_line >= end_line and end_line >= len(lines):
                break

        return chunks

    def chunk_repo(self, repo_path: Path, extensions: set[str] | None = None) -> list[CodeChunk]:
        """Recursively chunk all source files under *repo_path*."""
        if extensions is None:
            extensions = {".py", ".c", ".cpp", ".h", ".hpp", ".js", ".ts", ".go", ".java", ".rb", ".rs"}

        all_chunks: list[CodeChunk] = []
        for fp in sorted(repo_path.rglob("*")):
            if not fp.is_file():
                continue
            if fp.suffix not in extensions:
                continue
            # Skip hidden dirs and common noise
            parts = fp.relative_to(repo_path).parts
            if any(p.startswith(".") or p in {"node_modules", "__pycache__", ".git", "vendor", "venv", ".venv"} for p in parts):
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            rel = str(fp.relative_to(repo_path)).replace("\\", "/")
            all_chunks.extend(self.chunk_file(rel, content))

        logger.info("Chunked %d files into %d chunks under %s", len({c.file_path for c in all_chunks}), len(all_chunks), repo_path)
        return all_chunks


# ---------------------------------------------------------------------------
# 2. ImportGraphBuilder — shallow dependency graph from import statements
# ---------------------------------------------------------------------------

# Python: import X / from X import Y
_PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)|import\s+([\w.]+))", re.MULTILINE)

# C/C++: #include "file.h" or <file.h>
_C_INCLUDE_RE = re.compile(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]', re.MULTILINE)

# JS/TS: import ... from "path" / require("path")
_JS_IMPORT_RE = re.compile(r"""(?:from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""", re.MULTILINE)

# Go: import "path"
_GO_IMPORT_RE = re.compile(r'^\s*"([^"]+)"', re.MULTILINE)

# Java: import com.foo.Bar
_JAVA_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+);", re.MULTILINE)


class ImportGraphBuilder:
    """Build a shallow import / include adjacency graph for a repo.

    Returns ``{file_path: [imported_module_or_file, ...]}``.
    """

    def build(self, repo_path: Path, file_list: list[str] | None = None) -> dict[str, list[str]]:
        """Walk *repo_path* and extract imports for each file."""
        graph: dict[str, list[str]] = {}

        if file_list is None:
            file_list = [
                str(fp.relative_to(repo_path)).replace("\\", "/")
                for fp in sorted(repo_path.rglob("*"))
                if fp.is_file() and fp.suffix in {".py", ".c", ".cpp", ".h", ".hpp", ".js", ".ts", ".go", ".java", ".rb"}
            ]

        for rel in file_list:
            fp = repo_path / rel
            if not fp.is_file():
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            imports = self._extract_imports(rel, content)
            if imports:
                graph[rel] = imports

        return graph

    def _extract_imports(self, file_path: str, content: str) -> list[str]:
        ext = Path(file_path).suffix
        results: list[str] = []

        if ext == ".py":
            for m in _PY_IMPORT_RE.finditer(content):
                mod = m.group(1) or m.group(2)
                if mod:
                    results.append(mod)
        elif ext in {".c", ".cpp", ".h", ".hpp"}:
            for m in _C_INCLUDE_RE.finditer(content):
                results.append(m.group(1))
        elif ext in {".js", ".ts"}:
            for m in _JS_IMPORT_RE.finditer(content):
                mod = m.group(1) or m.group(2)
                if mod:
                    results.append(mod)
        elif ext == ".go":
            for m in _GO_IMPORT_RE.finditer(content):
                results.append(m.group(1))
        elif ext == ".java":
            for m in _JAVA_IMPORT_RE.finditer(content):
                results.append(m.group(1))

        return results


# ---------------------------------------------------------------------------
# 3. EmbeddingStore — sentence-transformers + FAISS index
# ---------------------------------------------------------------------------

_DEFAULT_EMBED_MODEL: str = "all-MiniLM-L6-v2"


class EmbeddingStore:
    """In-memory FAISS-backed embedding store for code chunks.

    Lazy-loads sentence-transformers and FAISS on first use so the module
    can be imported without heavy dependencies installed.
    """

    def __init__(self, model_name: str = _DEFAULT_EMBED_MODEL) -> None:
        self._model_name = model_name
        self._model: object | None = None
        self._index: object | None = None
        self._chunks: list[CodeChunk] = []
        self._dim: int | None = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for EmbeddingStore. "
                "Install with: pip install 'commitguard[v2]'"
            ) from exc
        self._model = SentenceTransformer(self._model_name)

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        try:
            import faiss
        except ImportError as exc:
            raise ImportError(
                "faiss-cpu is required for EmbeddingStore. "
                "Install with: pip install 'commitguard[v2]'"
            ) from exc
        if self._dim is None:
            self._ensure_model()
            # Probe dimension
            test_emb = self._model.encode(["test"], show_progress_bar=False)  # type: ignore[union-attr]
            self._dim = test_emb.shape[1]
        self._index = faiss.IndexFlatIP(self._dim)

    def add(self, chunks: list[CodeChunk]) -> None:
        """Embed and index a batch of code chunks."""
        if not chunks:
            return
        self._ensure_model()
        self._ensure_index()

        texts = [f"{c.file_path}\n{c.content}" for c in chunks]
        embeddings = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)  # type: ignore[union-attr]
        embeddings = np.asarray(embeddings, dtype=np.float32)

        self._index.add(embeddings)  # type: ignore[union-attr]
        self._chunks.extend(chunks)

    def search(self, query: str, top_k: int = 5) -> list[CodeChunk]:
        """Return the *top_k* most similar chunks to *query*."""
        if not self._chunks:
            return []
        self._ensure_model()
        self._ensure_index()

        q_emb = self._model.encode([query], show_progress_bar=False, normalize_embeddings=True)  # type: ignore[union-attr]
        q_emb = np.asarray(q_emb, dtype=np.float32)

        k = min(top_k, len(self._chunks))
        _scores, indices = self._index.search(q_emb, k)  # type: ignore[union-attr]

        return [self._chunks[i] for i in indices[0] if 0 <= i < len(self._chunks)]

    def clear(self) -> None:
        """Reset the index."""
        self._index = None
        self._chunks = []
        self._dim = None


# ---------------------------------------------------------------------------
# 4. ContextRetriever — combines embedding search with import graph
# ---------------------------------------------------------------------------


class ContextRetriever:
    """Retrieve cross-file context for a file under scan.

    Combines semantic similarity (via ``EmbeddingStore``) with import-graph
    adjacency to surface the most relevant chunks from the broader repo.
    """

    def __init__(
        self,
        store: EmbeddingStore,
        import_graph: dict[str, list[str]],
        *,
        top_k: int = 5,
        import_boost: float = 0.3,
    ) -> None:
        self._store = store
        self._graph = import_graph
        self._top_k = top_k
        self._import_boost = import_boost

    def retrieve(self, file_path: str, query: str, top_k: Optional[int] = None) -> list[CodeChunk]:
        """Return the most relevant chunks for *file_path* + *query*.

        Chunks from files in the import graph of *file_path* are boosted.
        """
        k = top_k or self._top_k
        # Fetch more candidates than needed so we can re-rank
        candidates = self._store.search(query, top_k=k * 3)

        # Determine related files from the import graph
        related: set[str] = set()
        for imp in self._graph.get(file_path, []):
            # Try to match import module to actual file paths
            imp_norm = imp.replace(".", "/")
            for chunk in candidates:
                if imp_norm in chunk.file_path:
                    related.add(chunk.file_path)

        # Re-rank: boost chunks from related files, deprioritize self
        scored: list[tuple[float, CodeChunk]] = []
        for i, chunk in enumerate(candidates):
            score = 1.0 - (i / max(1, len(candidates)))  # base: position-based
            if chunk.file_path in related:
                score += self._import_boost
            if chunk.file_path == file_path:
                score -= 0.1  # slight penalty to avoid self-retrieval
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:k]]
