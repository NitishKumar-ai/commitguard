"""Tests for commitguard_env.memory — chunking, import graphs, embedding store."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from commitguard_env.memory import CodeChunker, ImportGraphBuilder


# ---------------------------------------------------------------------------
# CodeChunker tests
# ---------------------------------------------------------------------------


class TestCodeChunker:
    """Test suite for the CodeChunker class."""

    def test_empty_file_returns_no_chunks(self) -> None:
        chunker = CodeChunker(chunk_tokens=100)
        result = chunker.chunk_file("empty.py", "")
        assert result == []

    def test_small_file_returns_single_chunk(self) -> None:
        chunker = CodeChunker(chunk_tokens=1000)
        content = "def hello():\n    return 'world'\n"
        result = chunker.chunk_file("hello.py", content)
        assert len(result) >= 1
        assert result[0].file_path == "hello.py"
        assert result[0].start_line == 1
        assert "hello" in result[0].content

    def test_large_file_produces_multiple_chunks(self) -> None:
        chunker = CodeChunker(chunk_tokens=10, stride_tokens=2)
        # Generate a file with many lines
        lines = [f"line_{i} = {i}" for i in range(100)]
        content = "\n".join(lines)
        result = chunker.chunk_file("big.py", content)
        assert len(result) > 1
        # Each chunk should have valid line numbers
        for chunk in result:
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
            assert chunk.token_count > 0

    def test_chunks_have_overlap(self) -> None:
        chunker = CodeChunker(chunk_tokens=20, stride_tokens=5)
        lines = [f"variable_{i} = {i}" for i in range(50)]
        content = "\n".join(lines)
        chunks = chunker.chunk_file("overlap.py", content)

        if len(chunks) >= 2:
            # Adjacent chunks should have some overlap
            first_end = chunks[0].end_line
            second_start = chunks[1].start_line
            assert second_start <= first_end, "Chunks should overlap"

    def test_chunk_repo_skips_hidden_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a visible file
            (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
            # Create a hidden dir file (should be skipped)
            (tmp_path / ".git").mkdir()
            (tmp_path / ".git" / "config").write_text("git config\n", encoding="utf-8")

            chunker = CodeChunker(chunk_tokens=1000)
            chunks = chunker.chunk_repo(tmp_path)

            files = {c.file_path for c in chunks}
            assert "main.py" in files
            assert ".git/config" not in files

    def test_chunk_repo_respects_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "code.py").write_text("x = 1\n", encoding="utf-8")
            (tmp_path / "readme.md").write_text("# Hi\n", encoding="utf-8")
            (tmp_path / "data.json").write_text("{}\n", encoding="utf-8")

            chunker = CodeChunker(chunk_tokens=1000)
            chunks = chunker.chunk_repo(tmp_path, extensions={".py"})

            files = {c.file_path for c in chunks}
            assert "code.py" in files
            assert "readme.md" not in files
            assert "data.json" not in files


# ---------------------------------------------------------------------------
# ImportGraphBuilder tests
# ---------------------------------------------------------------------------


class TestImportGraphBuilder:
    """Test suite for the ImportGraphBuilder."""

    def test_python_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "main.py").write_text(
                "import os\nfrom pathlib import Path\nimport json\n",
                encoding="utf-8",
            )

            builder = ImportGraphBuilder()
            graph = builder.build(tmp_path)

            assert "main.py" in graph
            assert "os" in graph["main.py"]
            assert "pathlib" in graph["main.py"]
            assert "json" in graph["main.py"]

    def test_c_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "main.c").write_text(
                '#include <stdio.h>\n#include "utils.h"\n',
                encoding="utf-8",
            )

            builder = ImportGraphBuilder()
            graph = builder.build(tmp_path)

            assert "main.c" in graph
            assert "stdio.h" in graph["main.c"]
            assert "utils.h" in graph["main.c"]

    def test_js_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "app.js").write_text(
                'import express from "express";\nconst fs = require("fs");\n',
                encoding="utf-8",
            )

            builder = ImportGraphBuilder()
            graph = builder.build(tmp_path)

            assert "app.js" in graph
            assert "express" in graph["app.js"]
            assert "fs" in graph["app.js"]

    def test_empty_file_no_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "empty.py").write_text("# no imports\nx = 1\n", encoding="utf-8")

            builder = ImportGraphBuilder()
            graph = builder.build(tmp_path)

            assert "empty.py" not in graph  # no imports = not in graph
