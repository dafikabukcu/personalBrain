# 🧠 Personal Brain

A **second brain assistant** that turns your Obsidian vault into a queryable knowledge base powered by AI. Ask questions in natural language and get answers with citations from your own notes.

## ✨ Features

- **🔍 Semantic Search** - Find notes by meaning, not just keywords
- **💬 Natural Language Q&A** - Ask questions like "What did I learn about X?"
- **📝 Quick Capture** - Add notes, tasks, and references from the command line
- **✅ Task Extraction** - Automatically extracts `- [ ]` tasks from your notes
- **📊 Daily Briefings** - AI-generated summary of your day's tasks and reminders
- **🔄 Real-time Sync** - Watch mode auto-indexes when you edit notes
- **🌐 REST API** - Integrate with other tools via HTTP endpoints
- **🔔 Notifications** - Desktop alerts and n8n webhook support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Obsidian Vault                           │
│                    (Markdown files + YAML)                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VaultWatcher                               │
│              (watchfiles - detects changes)                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MarkdownParser                               │
│     • Extract YAML frontmatter                                  │
│     • Parse #tags and [[wikilinks]]                            │
│     • Chunk by headers/paragraphs (512 chars max)              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│      SQLite DB        │   │   OpenAI Embeddings   │
│  • Document metadata  │   │  text-embedding-3-    │
│  • Tasks & reminders  │   │  small                │
│  • Personal facts     │   └───────────┬───────────┘
│  • Full-text search   │               │
└───────────────────────┘               ▼
                            ┌───────────────────────┐
                            │      ChromaDB         │
                            │   (Vector Store)      │
                            │  • Cosine similarity  │
                            │  • Metadata filtering │
                            └───────────┬───────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
              ┌───────────────────────┐   ┌───────────────────────┐
              │    Vector Search      │   │    BM25 Search        │
              │  (semantic meaning)   │   │  (keyword matching)   │
              └───────────┬───────────┘   └───────────┬───────────┘
                          │                           │
                          └─────────────┬─────────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   Hybrid Retriever    │
                            │  (RRF score fusion)   │
                            └───────────┬───────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │   Context Builder     │
                            │  (token management)   │
                            └───────────┬───────────┘
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │     Claude API        │
                            │  (answer generation)  │
                            └───────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.11 or 3.12 (not 3.13+ due to dependency constraints)
- An [OpenAI API key](https://platform.openai.com/api-keys) for embeddings
- An [Anthropic API key](https://console.anthropic.com/) for Claude

### Setup

```bash
# Clone the repository
git clone https://github.com/dafikabukcu/personalBrain.git
cd personalBrain

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

1. **Create `.env` file** in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
OPENAI_API_KEY=sk-xxxxx
N8N_WEBHOOK_URL=https://your-n8n.com/webhook/brain  # Optional
```

2. **Edit `config/default.yaml`** to set your vault path:

```yaml
vault:
  path: "D:\\obsdn\\Personal"  # Windows
  # path: "/Users/you/Documents/Obsidian/Vault"  # macOS/Linux
```

## 🚀 Usage

### Index Your Vault

```bash
# First-time indexing (processes all files)
brain index

# Incremental sync (only processes changes) - same command!
brain index

# Full rebuild (clears and re-indexes everything)
brain index --rebuild

# Watch mode (auto-index on file changes)
brain index --watch
```

### Ask Questions

```bash
# Basic query
brain ask "What have I learned about body language?"

# With source citations
brain ask "What are my goals for this year?" -v

# Example output:
# Based on your notes, you've written about reading micro-expressions
# and understanding limbic system responses...
#
# Sources:
#   • Cold Reading/12-Gövde Eğilmesi.md > Limbik Sistem
#   • Cold Reading/07-Beden Dilinin Aynası.md
```

### Quick Capture

```bash
# Capture a fleeting thought (saved to inbox/)
brain capture "Interesting idea about neural networks"

# Capture a task with due date (saved to tasks/)
brain capture "Review quarterly report" --type task --due 2025-01-25

# Capture with tags
brain capture "Meeting notes from standup" --tags work,meetings
```

### Manage Tasks

```bash
# List pending tasks
brain tasks

# List tasks due today
brain tasks --due today

# List all tasks (including completed)
brain tasks --status all

# Mark task as done
brain done 3
```

### Daily Briefing

```bash
# Get AI-generated daily briefing
brain briefing

# Output:
# ┌─────────────────────────────────────────┐
# │ Daily Briefing - Saturday, January 18   │
# └─────────────────────────────────────────┘
#
# 📋 Tasks Due Today:
#   • Review quarterly report
#   • Call dentist for appointment
#
# 🔔 Reminders:
#   • Team meeting at 2pm
#
# 📝 Summary:
#   You have 2 tasks due today focused on...
```

### Check Status

```bash
brain status

# Output:
# ┌─────────────────────────────────────┐
# │ Brain Status                        │
# ├─────────────────┬───────────────────┤
# │ Vault Path      │ D:\obsdn\Personal │
# │ Documents       │ 14                │
# │ Chunks          │ 125               │
# │ Tasks (Pending) │ 3                 │
# └─────────────────┴───────────────────┘
```

### Start API Server

```bash
# Start on default port 8000
brain serve

# Custom host/port
brain serve --host 0.0.0.0 --port 3000

# With auto-reload for development
brain serve --reload
```

## 🌐 API Endpoints

When running `brain serve`, these endpoints are available:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/query` | Semantic search with AI answer |
| `POST` | `/api/v1/query/stream` | Streaming response (SSE) |
| `POST` | `/api/v1/capture` | Quick capture a note |
| `GET` | `/api/v1/tasks` | List tasks |
| `PATCH` | `/api/v1/tasks/{id}` | Update task status |
| `GET` | `/api/v1/briefing` | Get daily briefing |
| `POST` | `/api/v1/index/rebuild` | Rebuild search index |
| `GET` | `/api/v1/index/status` | Index statistics |
| `GET` | `/api/v1/health` | Health check |

### Example API Usage

```bash
# Query your brain
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are my priorities?", "max_results": 5}'

# Capture a note
curl -X POST http://localhost:8000/api/v1/capture \
  -H "Content-Type: application/json" \
  -d '{"content": "Remember to buy milk", "type": "task"}'
```

## 📁 Vault Structure

Personal Brain works with **any folder structure**. It recursively indexes all `.md` files.

### Ignored Paths

- `.obsidian/` - Obsidian config
- `.trash/` - Deleted files
- `*.excalidraw.md` - Excalidraw drawings

### Supported Markdown Features

```markdown
---
title: My Note           # Extracted as document title
tags: [work, important]  # Indexed for filtering
created: 2025-01-18      # Stored as metadata
---

# Header 1

Content under headers is chunked separately for better retrieval.

## Header 2

- [ ] Unchecked task @due(2025-01-20)  ← Extracted as task
- [x] Completed task                    ← Marked as done

I prefer coffee over tea.  ← Can be extracted as personal fact

Check out [[Other Note]] for more info.  ← Wikilinks tracked

#inline-tags are also extracted
```

## 💰 Cost Breakdown

### Embeddings (OpenAI)

| Model | Price | Example |
|-------|-------|---------|
| `text-embedding-3-small` | $0.02 / 1M tokens | 100 notes ≈ $0.001 |

Embeddings are **cached locally** - you only pay once per unique text chunk.

### Chat (Claude)

| Model | Input | Output | Example Query |
|-------|-------|--------|---------------|
| Claude Sonnet | $3 / 1M | $15 / 1M | ~$0.005 per query |

### Typical Monthly Cost

| Usage | Estimated Cost |
|-------|----------------|
| 100 notes indexed | $0.01 |
| 50 queries/day | $7.50 |
| **Total** | **~$8/month** |

## 🔧 Configuration Reference

### `config/default.yaml`

```yaml
app:
  name: "Personal Brain"
  debug: false
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

vault:
  path: "D:\\obsdn\\Personal"
  watch_interval: 1.0  # seconds
  ignore_patterns:
    - ".obsidian/*"
    - ".trash/*"
    - "*.excalidraw.md"

database:
  sqlite_path: "./data/brain.db"
  chroma_path: "./data/chroma"

embeddings:
  provider: "openai"
  model: "text-embedding-3-small"
  batch_size: 100
  cache_enabled: true

claude:
  model: "claude-sonnet-4-20250514"
  max_tokens: 4096
  temperature: 0.7

retrieval:
  vector_weight: 0.7   # Semantic similarity weight
  bm25_weight: 0.3     # Keyword matching weight
  max_results: 20
  link_expansion_hops: 1  # Follow [[wikilinks]] this many levels

chunking:
  strategy: "semantic"  # Split by headers
  max_chunk_size: 512   # Characters per chunk
  overlap: 50

scheduler:
  briefing_time: "07:00"
  reminder_check_interval: 15  # minutes
  timezone: "UTC"

api:
  host: "127.0.0.1"
  port: 8000
  cors_origins:
    - "http://localhost:3000"

notifications:
  enabled: true
  desktop: true
  n8n:
    enabled: false
    webhook_url: ""
```

## 🛠️ Development

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=brain --cov-report=html

# Run specific test file
pytest tests/unit/test_markdown_parser.py
```

### Code Quality

```bash
# Lint with ruff
ruff check src/

# Type check with mypy
mypy src/

# Format code
ruff format src/
```

### Project Structure

```
personal-brain/
├── src/brain/
│   ├── core/           # Data models, config, extractors
│   ├── data/           # Vault watcher, parsers, storage
│   ├── intelligence/   # Embeddings, retrieval, Claude client
│   ├── agency/         # Scheduler, notifications
│   ├── api/            # FastAPI routes
│   ├── cli/            # Typer CLI commands
│   └── web/            # Web UI templates (future)
├── tests/
├── config/
└── data/               # SQLite + ChromaDB (gitignored)
```

## 🗺️ Roadmap

- [ ] Web UI with chat interface
- [ ] Periodic review suggestions ("revisit notes from 2 weeks ago")
- [ ] Multi-vault support
- [ ] Obsidian plugin for seamless integration
- [ ] Local LLM support (Ollama)
- [ ] Graph visualization of note connections

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [Obsidian](https://obsidian.md/) - The best knowledge management tool
- [ChromaDB](https://www.trychroma.com/) - Embedded vector database
- [Claude](https://anthropic.com/) - AI that actually understands context
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Typer](https://typer.tiangolo.com/) - CLI framework with great UX
