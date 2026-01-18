"""Pytest configuration and fixtures."""

import tempfile
from pathlib import Path

import pytest

from brain.core.config import Config, VaultConfig, DatabaseConfig


@pytest.fixture
def temp_vault(tmp_path):
    """Create a temporary vault with sample notes."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Create sample notes
    (vault / "note1.md").write_text("""---
title: Test Note 1
tags: [test, sample]
---

# Test Note 1

This is a test note with some content.

## Section 1

Some text in section 1.

- [ ] Task 1 @due(2025-01-20)
- [x] Completed task

## Section 2

More content here with a [[link to note2]].
""")

    (vault / "note2.md").write_text("""---
title: Test Note 2
---

# Test Note 2

Another test note referenced by note1.

I prefer coffee over tea.
""")

    return vault


@pytest.fixture
def test_config(tmp_path, temp_vault):
    """Create test configuration."""
    db_path = tmp_path / "data"
    db_path.mkdir()

    return Config(
        vault=VaultConfig(path=temp_vault),
        database=DatabaseConfig(
            sqlite_path=db_path / "brain.db",
            chroma_path=db_path / "chroma",
        ),
        anthropic_api_key="test-key",
        openai_api_key="test-key",
    )
