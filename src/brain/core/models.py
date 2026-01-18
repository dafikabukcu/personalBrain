"""Core data models using Pydantic."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enum."""

    PENDING = "pending"
    DONE = "done"
    CANCELLED = "cancelled"


class ChunkType(str, Enum):
    """Chunk type enum."""

    HEADER = "header"
    PARAGRAPH = "paragraph"
    LIST = "list"
    CODE = "code"
    BLOCKQUOTE = "blockquote"


class FactCategory(str, Enum):
    """Fact category enum."""

    PREFERENCE = "preference"
    CONTACT = "contact"
    DECISION = "decision"
    GOAL = "goal"
    OTHER = "other"


class Document(BaseModel):
    """Represents a parsed markdown document."""

    id: str = Field(..., description="Unique identifier (hash of path)")
    path: str = Field(..., description="Relative path from vault root")
    title: str = Field(default="", description="Document title")
    content: str = Field(default="", description="Raw markdown content")
    checksum: str = Field(default="", description="Content hash for change detection")
    created_at: datetime | None = None
    modified_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list, description="[[wikilinks]]")
    frontmatter: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    """Represents a chunk of a document for embedding."""

    id: str = Field(..., description="Unique chunk ID: doc_id:chunk_idx")
    document_id: str
    document_path: str
    chunk_index: int
    chunk_type: ChunkType = ChunkType.PARAGRAPH
    content: str
    header_path: str = Field(default="", description="Nested header context")
    char_start: int = 0
    char_end: int = 0
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    created_date: str | None = None


class Task(BaseModel):
    """Represents a task extracted from notes."""

    id: int | None = None
    document_id: str | None = None
    content: str
    status: TaskStatus = TaskStatus.PENDING
    due_date: datetime | None = None
    priority: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    source_line: int | None = None


class Reminder(BaseModel):
    """Represents a reminder."""

    id: int | None = None
    document_id: str | None = None
    content: str
    trigger_date: datetime | None = None
    trigger_condition: dict[str, Any] | None = None
    is_triggered: bool = False
    created_at: datetime = Field(default_factory=datetime.now)


class Fact(BaseModel):
    """Represents a personal fact (preference, contact, decision)."""

    id: int | None = None
    document_id: str | None = None
    category: FactCategory = FactCategory.OTHER
    subject: str = ""
    content: str
    confidence: float = 1.0
    extracted_at: datetime = Field(default_factory=datetime.now)


class SearchResult(BaseModel):
    """A single search result."""

    chunk: Chunk
    score: float
    source: str = Field(default="vector", description="vector or bm25")


class QueryResult(BaseModel):
    """Result of a query to the brain."""

    query: str
    answer: str
    sources: list[SearchResult] = Field(default_factory=list)
    confidence: float = 0.0
    processing_time_ms: float = 0.0


class Briefing(BaseModel):
    """Daily briefing model."""

    date: datetime
    tasks_due: list[Task] = Field(default_factory=list)
    reminders: list[Reminder] = Field(default_factory=list)
    context_notes: list[Document] = Field(default_factory=list)
    suggested_reviews: list[str] = Field(default_factory=list)
    summary: str = ""
