"""Tests for markdown parser."""

from pathlib import Path

import pytest

from brain.data.markdown_parser import MarkdownParser
from brain.core.models import ChunkType


@pytest.fixture
def parser():
    return MarkdownParser(max_chunk_size=200, overlap=20)


@pytest.fixture
def sample_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def test_parse_simple_note(parser, sample_vault):
    """Test parsing a simple markdown note."""
    note_path = sample_vault / "test.md"
    note_path.write_text("""---
title: Test Note
tags: [test, sample]
---

# Test Note

This is a test paragraph.
""")

    doc = parser.parse(note_path, sample_vault)

    assert doc.title == "Test Note"
    assert "test" in doc.tags
    assert "sample" in doc.tags
    assert doc.path == "test.md"


def test_parse_extracts_wikilinks(parser, sample_vault):
    """Test that wikilinks are extracted."""
    note_path = sample_vault / "test.md"
    note_path.write_text("""# Test

Check out [[Other Note]] and [[Another|display text]].
""")

    doc = parser.parse(note_path, sample_vault)

    assert "Other Note" in doc.links
    assert "Another" in doc.links


def test_parse_extracts_tags_from_content(parser, sample_vault):
    """Test that inline tags are extracted."""
    note_path = sample_vault / "test.md"
    note_path.write_text("""# Test

This note is about #python and #coding.
""")

    doc = parser.parse(note_path, sample_vault)

    assert "python" in doc.tags
    assert "coding" in doc.tags


def test_chunk_by_headers(parser, sample_vault):
    """Test chunking by headers."""
    note_path = sample_vault / "test.md"
    note_path.write_text("""# Main Title

Intro paragraph.

## Section 1

Content of section 1.

## Section 2

Content of section 2.
""")

    doc = parser.parse(note_path, sample_vault)
    chunks = parser.chunk(doc)

    assert len(chunks) >= 2
    # Check header paths are set
    header_paths = [c.header_path for c in chunks]
    assert any("Section 1" in h for h in header_paths)
    assert any("Section 2" in h for h in header_paths)


def test_chunk_respects_max_size(parser, sample_vault):
    """Test that chunks respect max size."""
    note_path = sample_vault / "test.md"
    long_content = "This is a sentence. " * 50
    note_path.write_text(f"# Test\n\n{long_content}")

    doc = parser.parse(note_path, sample_vault)
    chunks = parser.chunk(doc)

    for chunk in chunks:
        assert len(chunk.content) <= parser.max_chunk_size + 50  # Allow some overflow


def test_extract_tasks(parser):
    """Test task extraction."""
    content = """
- [ ] Pending task @due(2025-01-20)
- [x] Completed task
- [ ] Another task
"""
    tasks = parser.extract_tasks(content)

    assert len(tasks) == 3
    assert tasks[0]["content"] == "Pending task @due(2025-01-20)"
    assert tasks[0]["is_done"] is False
    assert tasks[0]["due_date"] == "2025-01-20"
    assert tasks[1]["is_done"] is True


def test_detect_chunk_type(parser):
    """Test chunk type detection."""
    assert parser._detect_chunk_type("```python\ncode\n```") == ChunkType.CODE
    assert parser._detect_chunk_type("> Quote text") == ChunkType.BLOCKQUOTE
    assert parser._detect_chunk_type("- List item") == ChunkType.LIST
    assert parser._detect_chunk_type("1. Numbered item") == ChunkType.LIST
    assert parser._detect_chunk_type("Regular paragraph") == ChunkType.PARAGRAPH
