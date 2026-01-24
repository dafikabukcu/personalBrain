"""Main CLI application using Typer."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from brain.core.config import get_config
from brain.service import BrainService

# Fix Unicode encoding on Windows (Turkish chars in file paths)
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

app = typer.Typer(
    name="brain",
    help="Your Second Brain CLI - Query and manage your personal knowledge base.",
    no_args_is_help=True,
)
console = Console(force_terminal=False)


def get_service() -> BrainService:
    """Get initialized brain service."""
    config = get_config()
    return BrainService(config)


@app.command()
def ask(
    query: str = typer.Argument(..., help="Your question"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show sources"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response"),
):
    """Ask a question about your notes."""
    service = get_service()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Searching...", total=None)
        result = service.query(query)

    console.print()
    console.print(Markdown(result.answer))

    if verbose and result.sources:
        console.print()
        console.print("[dim]Sources:[/dim]")
        for src in result.sources[:5]:
            path = src.chunk.document_path
            header = src.chunk.header_path
            console.print(f"  [blue]•[/blue] {path}" + (f" > {header}" if header else ""))


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text, json, markdown"),
):
    """Search notes and return raw chunks (no AI summarization).

    Use this when integrating with other AI agents (e.g., Clawdbot/Jenna)
    to avoid double LLM calls. The agent can read the chunks directly.
    """
    import json

    service = get_service()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Searching...", total=None)
        results = service.search(query, k=limit)

    if not results:
        if format == "json":
            console.print("[]")
        else:
            console.print("[dim]No results found.[/dim]")
        return

    if format == "json":
        output = [
            {
                "content": r.chunk.content,
                "path": r.chunk.document_path,
                "header": r.chunk.header_path or None,
                "score": round(r.score, 4),
                "source": r.source,
            }
            for r in results
        ]
        console.print(json.dumps(output, indent=2, ensure_ascii=False))

    elif format == "markdown":
        for i, r in enumerate(results, 1):
            console.print(f"## Result {i}: {r.chunk.document_path}")
            if r.chunk.header_path:
                console.print(f"*Section: {r.chunk.header_path}*\n")
            console.print(r.chunk.content)
            console.print(f"\n*Score: {r.score:.4f} ({r.source})*")
            console.print("\n---\n")

    else:  # text format
        for i, r in enumerate(results, 1):
            console.print(f"[blue]── Result {i} ──[/blue] [dim]{r.chunk.document_path}[/dim]")
            if r.chunk.header_path:
                console.print(f"[dim]Section: {r.chunk.header_path}[/dim]")
            console.print(r.chunk.content)
            console.print(f"[dim]Score: {r.score:.4f} ({r.source})[/dim]")
            console.print()


@app.command()
def capture(
    content: str = typer.Argument(..., help="Content to capture"),
    type: str = typer.Option("fleeting", "--type", "-t", help="Note type: fleeting, task, reference"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    due: Optional[str] = typer.Option(None, "--due", help="Due date for tasks (YYYY-MM-DD or 'tomorrow')"),
):
    """Quickly capture a thought, task, or reference."""
    service = get_service()

    tag_list = [t.strip() for t in tags.split(",")] if tags else []

    result = service.capture(
        content=content,
        note_type=type,
        tags=tag_list,
        due_date=due,
    )

    console.print(f"[green]✓[/green] Captured to: {result['file_path']}")


@app.command()
def tasks(
    status: str = typer.Option("pending", "--status", "-s", help="Filter by status: pending, done, all"),
    due: Optional[str] = typer.Option(None, "--due", help="Filter by due date: today, week, or YYYY-MM-DD"),
):
    """List and manage tasks."""
    service = get_service()
    task_list = service.get_tasks(status=status, due_filter=due)

    if not task_list:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(title="Tasks", show_header=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Task", style="white")
    table.add_column("Due", style="yellow", width=12)
    table.add_column("Status", width=10)

    for task in task_list:
        status_style = "green" if task.status.value == "done" else "white"
        due_str = task.due_date.strftime("%Y-%m-%d") if task.due_date else "-"
        table.add_row(
            str(task.id),
            task.content[:60] + ("..." if len(task.content) > 60 else ""),
            due_str,
            f"[{status_style}]{task.status.value}[/{status_style}]",
        )

    console.print(table)


@app.command()
def done(
    task_id: int = typer.Argument(..., help="Task ID to mark as done"),
):
    """Mark a task as done."""
    service = get_service()
    service.complete_task(task_id)
    console.print(f"[green]✓[/green] Task {task_id} marked as done.")


@app.command()
def briefing():
    """Show today's briefing."""
    service = get_service()
    brief = service.generate_briefing()

    console.print(Panel(f"[bold]Daily Briefing - {brief.date.strftime('%A, %B %d')}[/bold]"))

    if brief.tasks_due:
        console.print("\n[bold yellow]📋 Tasks Due Today:[/bold yellow]")
        for task in brief.tasks_due:
            console.print(f"  • {task.content}")

    if brief.reminders:
        console.print("\n[bold blue]🔔 Reminders:[/bold blue]")
        for reminder in brief.reminders:
            console.print(f"  • {reminder.content}")

    if brief.suggested_reviews:
        console.print("\n[bold magenta]📝 Suggested Reviews:[/bold magenta]")
        for review in brief.suggested_reviews:
            console.print(f"  • {review}")

    if brief.summary:
        console.print("\n[bold]Summary:[/bold]")
        console.print(Markdown(brief.summary))


@app.command()
def index(
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch for changes"),
    rebuild: bool = typer.Option(False, "--rebuild", help="Rebuild entire index"),
):
    """Index your vault or watch for changes."""
    service = get_service()

    if rebuild:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Rebuilding index...", total=None)
            stats = service.rebuild_index()
            progress.update(task, completed=True)

        console.print(f"[green]✓[/green] Indexed {stats['documents']} documents, {stats['chunks']} chunks")
        return

    if watch:
        console.print("[blue]Watching vault for changes... Press Ctrl+C to stop.[/blue]")
        import asyncio
        try:
            asyncio.run(service.watch_vault())
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped watching.[/yellow]")
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Syncing index...", total=None)
            stats = service.sync_index()
            progress.update(task, completed=True)

        console.print(f"[green]✓[/green] Synced: {stats['added']} added, {stats['updated']} updated, {stats['deleted']} deleted")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the API server."""
    import uvicorn

    console.print(f"[green]Starting server at http://{host}:{port}[/green]")
    uvicorn.run(
        "brain.api.app:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def status():
    """Show brain status and statistics."""
    service = get_service()
    stats = service.get_stats()

    table = Table(title="Brain Status", show_header=False)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Vault Path", str(stats["vault_path"]))
    table.add_row("Documents", str(stats["documents"]))
    table.add_row("Chunks", str(stats["chunks"]))
    table.add_row("Tasks (Pending)", str(stats["tasks_pending"]))
    table.add_row("Last Indexed", stats["last_indexed"] or "Never")

    console.print(table)


if __name__ == "__main__":
    app()
