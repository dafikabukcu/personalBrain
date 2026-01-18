"""Main Brain service that orchestrates all components."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
from watchfiles import Change

from brain.core.config import Config
from brain.core.models import Briefing, QueryResult, SearchResult, Task, TaskStatus
from brain.data.markdown_parser import MarkdownParser
from brain.data.sqlite_store import SQLiteStore
from brain.data.vault_watcher import VaultWatcher
from brain.data.vector_store import VectorStore
from brain.intelligence.claude_client import ClaudeClient
from brain.intelligence.context_builder import ContextBuilder
from brain.intelligence.embeddings import EmbeddingService
from brain.intelligence.retriever import HybridRetriever

logger = structlog.get_logger()


class BrainService:
    """Main service orchestrating all brain components."""

    def __init__(self, config: Config):
        self.config = config

        # Initialize data stores
        self.sqlite_store = SQLiteStore(config.database.sqlite_path)
        self.vector_store = VectorStore(config.database.chroma_path)

        # Initialize parser
        self.parser = MarkdownParser(
            max_chunk_size=config.chunking.max_chunk_size,
            overlap=config.chunking.overlap,
        )

        # Initialize vault watcher
        self.vault_watcher = VaultWatcher(
            vault_path=config.vault.path,
            ignore_patterns=config.vault.ignore_patterns,
        )

        # Initialize intelligence layer
        self.embedding_service = EmbeddingService(
            api_key=config.openai_api_key,
            model=config.embeddings.model,
            batch_size=config.embeddings.batch_size,
            cache_path=config.database.chroma_path / "embedding_cache.json"
            if config.embeddings.cache_enabled
            else None,
        )

        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            embedding_service=self.embedding_service,
            vector_weight=config.retrieval.vector_weight,
            bm25_weight=config.retrieval.bm25_weight,
        )

        self.claude_client = ClaudeClient(
            api_key=config.anthropic_api_key,
            model=config.claude.model,
            max_tokens=config.claude.max_tokens,
            temperature=config.claude.temperature,
        )

        self.context_builder = ContextBuilder(max_tokens=8000)

        logger.info("brain_service_initialized", vault_path=str(config.vault.path))

    def query(self, question: str, k: int = 10) -> QueryResult:
        """Query the brain with a question."""
        start_time = datetime.now()

        # Retrieve relevant chunks
        results = self.retriever.retrieve(question, k=k)

        # Build context
        context = self.context_builder.build(results)

        # Generate answer
        sources_info = [
            {"path": r.chunk.document_path, "header": r.chunk.header_path}
            for r in results
        ]
        answer = self.claude_client.answer_question(
            question=question,
            context=context,
            sources=sources_info,
        )

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return QueryResult(
            query=question,
            answer=answer,
            sources=results,
            confidence=results[0].score if results else 0.0,
            processing_time_ms=processing_time,
        )

    def capture(
        self,
        content: str,
        note_type: str = "fleeting",
        tags: list[str] | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any]:
        """Capture a new note."""
        tags = tags or []
        now = datetime.now()

        # Determine target file
        if note_type == "task":
            folder = "tasks"
            # Parse due date
            if due_date:
                if due_date == "tomorrow":
                    parsed_due = now + timedelta(days=1)
                else:
                    parsed_due = datetime.strptime(due_date, "%Y-%m-%d")
                content = f"- [ ] {content} @due({parsed_due.strftime('%Y-%m-%d')})"
        elif note_type == "reference":
            folder = "references"
        else:
            folder = "inbox"

        # Create file path
        date_str = now.strftime("%Y-%m-%d")
        file_name = f"{date_str}-{now.strftime('%H%M%S')}.md"
        file_path = self.config.vault.path / folder / file_name

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Build note content
        frontmatter = f"""---
created: {now.isoformat()}
type: {note_type}
tags: [{', '.join(tags)}]
---

"""
        full_content = frontmatter + content

        # Write file
        file_path.write_text(full_content, encoding="utf-8")

        # Index immediately
        self._index_file(file_path)

        logger.info("note_captured", path=str(file_path), type=note_type)

        return {
            "file_path": str(file_path.relative_to(self.config.vault.path)),
            "type": note_type,
        }

    def get_tasks(
        self,
        status: str = "pending",
        due_filter: str | None = None,
    ) -> list[Task]:
        """Get tasks with optional filters."""
        task_status = None if status == "all" else TaskStatus(status)

        due_before = None
        if due_filter:
            if due_filter == "today":
                due_before = datetime.now().replace(hour=23, minute=59, second=59)
            elif due_filter == "week":
                due_before = datetime.now() + timedelta(days=7)
            else:
                due_before = datetime.strptime(due_filter, "%Y-%m-%d")

        return self.sqlite_store.get_tasks(status=task_status, due_before=due_before)

    def complete_task(self, task_id: int) -> None:
        """Mark a task as complete."""
        self.sqlite_store.update_task_status(task_id, TaskStatus.DONE)

    def generate_briefing(self) -> Briefing:
        """Generate daily briefing."""
        today = datetime.now()
        tomorrow = today + timedelta(days=1)

        # Get tasks due today
        tasks_due = self.sqlite_store.get_tasks(
            status=TaskStatus.PENDING,
            due_before=tomorrow,
        )

        # Get due reminders
        reminders = self.sqlite_store.get_due_reminders(before=tomorrow)

        # Get suggested reviews (notes not accessed in 2 weeks)
        # This would require tracking access, simplified for now
        suggested_reviews: list[str] = []

        # Generate summary using Claude
        context_parts = []
        if tasks_due:
            context_parts.append("Tasks due today:\n" + "\n".join(f"- {t.content}" for t in tasks_due))
        if reminders:
            context_parts.append("Reminders:\n" + "\n".join(f"- {r.content}" for r in reminders))

        summary = ""
        if context_parts:
            summary = self.claude_client.complete(
                prompt="Generate a brief, encouraging daily briefing summary based on this information. Keep it to 2-3 sentences.",
                context="\n\n".join(context_parts),
                temperature=0.7,
            )

        return Briefing(
            date=today,
            tasks_due=tasks_due,
            reminders=reminders,
            suggested_reviews=suggested_reviews,
            summary=summary,
        )

    def rebuild_index(self) -> dict[str, int]:
        """Rebuild the entire index."""
        # Clear existing data
        self.vector_store.clear()

        # Scan all files
        files = self.vault_watcher.scan_all()
        total_chunks = 0

        for file_path in files:
            chunks = self._index_file(file_path)
            total_chunks += len(chunks)

        self.retriever.mark_dirty()

        return {"documents": len(files), "chunks": total_chunks}

    def sync_index(self) -> dict[str, int]:
        """Sync index with vault changes."""
        existing_checksums = self.sqlite_store.get_all_document_checksums()
        existing_ids = set(existing_checksums.keys())

        # Scan current files
        files = self.vault_watcher.scan_all()
        current_paths: dict[str, Path] = {}

        for file_path in files:
            relative_path = str(file_path.relative_to(self.config.vault.path)).replace("\\", "/")
            import hashlib
            doc_id = hashlib.sha256(relative_path.encode()).hexdigest()[:16]
            current_paths[doc_id] = file_path

        current_ids = set(current_paths.keys())

        # Find changes
        added_ids = current_ids - existing_ids
        deleted_ids = existing_ids - current_ids
        potential_updated = current_ids & existing_ids

        added = 0
        updated = 0
        deleted = 0

        # Process additions
        for doc_id in added_ids:
            self._index_file(current_paths[doc_id])
            added += 1

        # Process updates
        for doc_id in potential_updated:
            file_path = current_paths[doc_id]
            content = file_path.read_text(encoding="utf-8")
            import hashlib
            current_checksum = hashlib.md5(content.encode()).hexdigest()

            if current_checksum != existing_checksums.get(doc_id):
                # Re-index
                self.vector_store.delete_by_document(doc_id)
                self._index_file(file_path)
                updated += 1

        # Process deletions
        for doc_id in deleted_ids:
            self.vector_store.delete_by_document(doc_id)
            self.sqlite_store.delete_document(doc_id)
            deleted += 1

        if added or updated or deleted:
            self.retriever.mark_dirty()

        return {"added": added, "updated": updated, "deleted": deleted}

    async def watch_vault(self) -> None:
        """Watch vault for changes and index automatically."""
        async def on_change(change: Change, path: Path) -> None:
            if change == Change.deleted:
                # Handle deletion
                relative_path = str(path.relative_to(self.config.vault.path)).replace("\\", "/")
                import hashlib
                doc_id = hashlib.sha256(relative_path.encode()).hexdigest()[:16]
                self.vector_store.delete_by_document(doc_id)
                self.sqlite_store.delete_document(doc_id)
                logger.info("document_deleted", path=relative_path)
            else:
                # Handle add/modify
                self._index_file(path)
                logger.info("document_indexed", path=str(path))

            self.retriever.mark_dirty()

        self.vault_watcher.on_change(on_change)
        await self.vault_watcher.start()

        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            await self.vault_watcher.stop()

    def _index_file(self, file_path: Path) -> list:
        """Index a single file."""
        # Parse document
        doc = self.parser.parse(file_path, self.config.vault.path)

        # Store document metadata
        self.sqlite_store.upsert_document(doc)

        # Extract tasks
        tasks = self.parser.extract_tasks(doc.content)
        for task_data in tasks:
            task = Task(
                document_id=doc.id,
                content=task_data["content"],
                status=TaskStatus.DONE if task_data["is_done"] else TaskStatus.PENDING,
                due_date=datetime.strptime(task_data["due_date"], "%Y-%m-%d") if task_data["due_date"] else None,
                source_line=task_data["line"],
            )
            self.sqlite_store.add_task(task)

        # Chunk document
        chunks = self.parser.chunk(doc)

        if chunks:
            # Generate embeddings
            texts = [c.content for c in chunks]
            embeddings = self.embedding_service.embed(texts)

            # Store in vector DB
            self.vector_store.upsert(chunks, embeddings)

        return chunks

    def get_stats(self) -> dict[str, Any]:
        """Get brain statistics."""
        pending_tasks = len(self.sqlite_store.get_tasks(status=TaskStatus.PENDING))

        return {
            "vault_path": str(self.config.vault.path),
            "documents": len(self.sqlite_store.get_all_document_checksums()),
            "chunks": self.vector_store.count(),
            "tasks_pending": pending_tasks,
            "last_indexed": None,  # Could track this in SQLite
        }
