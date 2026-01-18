"""Structured data extractors using Claude."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from brain.core.models import Fact, FactCategory, Reminder, Task, TaskStatus
from brain.intelligence.claude_client import ClaudeClient


class ExtractedTask(BaseModel):
    """Extracted task model."""

    content: str
    due_date: str | None = None
    priority: int = 0


class ExtractedReminder(BaseModel):
    """Extracted reminder model."""

    content: str
    trigger_date: str | None = None
    trigger_condition: str | None = None


class ExtractedFact(BaseModel):
    """Extracted personal fact model."""

    category: str
    subject: str
    content: str
    confidence: float = 1.0


class ExtractionResult(BaseModel):
    """Combined extraction result."""

    tasks: list[ExtractedTask] = Field(default_factory=list)
    reminders: list[ExtractedReminder] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)


class StructuredExtractor:
    """Extract structured data from note content."""

    def __init__(self, claude_client: ClaudeClient):
        self.claude_client = claude_client

    def extract_all(self, content: str, document_id: str) -> dict[str, list[Any]]:
        """Extract all structured data from content."""
        result = self.claude_client.extract(
            text=content,
            schema=ExtractionResult,
            instructions="""Extract the following from the text:
1. Tasks: Any action items, todos, or things to do. Look for checkbox items, phrases like "need to", "should", "must", etc.
2. Reminders: Time-based notifications or scheduled events. Look for dates, deadlines, appointments.
3. Facts: Personal information about preferences, contacts, decisions, or goals. Look for statements like "I prefer", "I decided", "My favorite", contact information, etc.

For categories, use: preference, contact, decision, goal, or other.""",
        )

        if not result:
            return {"tasks": [], "reminders": [], "facts": []}

        # Convert to domain models
        tasks = [
            Task(
                document_id=document_id,
                content=t.content,
                due_date=datetime.strptime(t.due_date, "%Y-%m-%d") if t.due_date else None,
                priority=t.priority,
                status=TaskStatus.PENDING,
            )
            for t in result.tasks
        ]

        reminders = [
            Reminder(
                document_id=document_id,
                content=r.content,
                trigger_date=datetime.fromisoformat(r.trigger_date) if r.trigger_date else None,
            )
            for r in result.reminders
        ]

        facts = [
            Fact(
                document_id=document_id,
                category=FactCategory(f.category) if f.category in [e.value for e in FactCategory] else FactCategory.OTHER,
                subject=f.subject,
                content=f.content,
                confidence=f.confidence,
            )
            for f in result.facts
        ]

        return {"tasks": tasks, "reminders": reminders, "facts": facts}

    def extract_tasks_only(self, content: str, document_id: str) -> list[Task]:
        """Extract only tasks from content."""
        result = self.extract_all(content, document_id)
        return result["tasks"]

    def extract_facts_only(self, content: str, document_id: str) -> list[Fact]:
        """Extract only facts from content."""
        result = self.extract_all(content, document_id)
        return result["facts"]
