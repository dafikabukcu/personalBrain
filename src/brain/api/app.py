"""FastAPI application for brain service."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from brain.core.config import get_config
from brain.service import BrainService

# Global service instance
_service: BrainService | None = None


def get_service() -> BrainService:
    """Get brain service instance."""
    global _service
    if _service is None:
        config = get_config()
        _service = BrainService(config)
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    _ = get_service()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="Personal Brain API",
    description="API for your second brain assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---


class QueryRequest(BaseModel):
    """Query request model."""

    query: str
    filters: dict[str, Any] | None = None
    max_results: int = 10
    include_sources: bool = True


class QueryResponse(BaseModel):
    """Query response model."""

    answer: str
    sources: list[dict[str, Any]] | None = None
    confidence: float
    processing_time_ms: float


class CaptureRequest(BaseModel):
    """Capture request model."""

    content: str
    type: str = "fleeting"
    tags: list[str] | None = None
    due_date: str | None = None


class CaptureResponse(BaseModel):
    """Capture response model."""

    id: str
    file_path: str


class TaskResponse(BaseModel):
    """Task response model."""

    id: int
    content: str
    status: str
    due_date: str | None
    priority: int


class BriefingResponse(BaseModel):
    """Briefing response model."""

    date: str
    tasks_due: list[TaskResponse]
    reminders: list[dict[str, Any]]
    suggested_reviews: list[str]
    summary: str


class IndexStatusResponse(BaseModel):
    """Index status response model."""

    total_documents: int
    total_chunks: int
    last_indexed: str | None


# --- Routes ---


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Query the brain with a question."""
    service = get_service()
    result = service.query(request.query, k=request.max_results)

    sources = None
    if request.include_sources:
        sources = [
            {
                "path": r.chunk.document_path,
                "header": r.chunk.header_path,
                "score": r.score,
                "content_preview": r.chunk.content[:200],
            }
            for r in result.sources
        ]

    return QueryResponse(
        answer=result.answer,
        sources=sources,
        confidence=result.confidence,
        processing_time_ms=result.processing_time_ms,
    )


@app.post("/api/v1/query/stream")
async def query_stream(request: QueryRequest):
    """Stream a query response."""
    service = get_service()

    # Get context first
    results = service.retriever.retrieve(request.query, k=request.max_results)
    context = service.context_builder.build(results)

    async def generate():
        for chunk in service.claude_client.complete_stream(
            prompt=request.query,
            context=context,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/v1/capture", response_model=CaptureResponse)
async def capture(request: CaptureRequest):
    """Capture a new note."""
    service = get_service()
    result = service.capture(
        content=request.content,
        note_type=request.type,
        tags=request.tags,
        due_date=request.due_date,
    )
    return CaptureResponse(
        id=result["file_path"].split("/")[-1].replace(".md", ""),
        file_path=result["file_path"],
    )


@app.get("/api/v1/tasks", response_model=list[TaskResponse])
async def get_tasks(
    status: str = "pending",
    due_before: str | None = None,
):
    """Get tasks."""
    service = get_service()
    tasks = service.get_tasks(status=status, due_filter=due_before)
    return [
        TaskResponse(
            id=t.id or 0,
            content=t.content,
            status=t.status.value,
            due_date=t.due_date.isoformat() if t.due_date else None,
            priority=t.priority,
        )
        for t in tasks
    ]


@app.patch("/api/v1/tasks/{task_id}")
async def update_task(task_id: int, status: str):
    """Update task status."""
    service = get_service()
    try:
        from brain.core.models import TaskStatus
        service.sqlite_store.update_task_status(task_id, TaskStatus(status))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/briefing", response_model=BriefingResponse)
async def get_briefing():
    """Get today's briefing."""
    service = get_service()
    briefing = service.generate_briefing()
    return BriefingResponse(
        date=briefing.date.isoformat(),
        tasks_due=[
            TaskResponse(
                id=t.id or 0,
                content=t.content,
                status=t.status.value,
                due_date=t.due_date.isoformat() if t.due_date else None,
                priority=t.priority,
            )
            for t in briefing.tasks_due
        ],
        reminders=[
            {"id": r.id, "content": r.content, "trigger_date": r.trigger_date.isoformat() if r.trigger_date else None}
            for r in briefing.reminders
        ],
        suggested_reviews=briefing.suggested_reviews,
        summary=briefing.summary,
    )


@app.post("/api/v1/index/rebuild")
async def rebuild_index():
    """Rebuild the entire index."""
    service = get_service()
    stats = service.rebuild_index()
    return {"status": "ok", "documents_indexed": stats["documents"], "chunks": stats["chunks"]}


@app.get("/api/v1/index/status", response_model=IndexStatusResponse)
async def index_status():
    """Get index status."""
    service = get_service()
    stats = service.get_stats()
    return IndexStatusResponse(
        total_documents=stats["documents"],
        total_chunks=stats["chunks"],
        last_indexed=stats["last_indexed"],
    )


@app.get("/api/v1/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
