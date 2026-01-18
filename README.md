# Personal Brain

A second brain assistant powered by Obsidian and Claude.

## Features

- **Semantic Search**: Query your notes using natural language
- **Hybrid Retrieval**: Combines vector similarity with BM25 keyword search
- **Task Management**: Extract and track tasks from your notes
- **Daily Briefings**: Automated morning briefings with tasks and reminders
- **Quick Capture**: Capture thoughts, tasks, and references from CLI
- **API & Web UI**: REST API and web interface

## Installation

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys
```

## Configuration

Edit `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Edit `config/default.yaml` to set your vault path.

## Usage

```bash
# Index your vault
brain index

# Ask questions
brain ask "What did I discuss with John last week?"

# Capture notes
brain capture "Remember to call Alice" --type task --due tomorrow

# View tasks
brain tasks

# Daily briefing
brain briefing

# Watch for changes
brain index --watch

# Start API server
brain serve
```

## API Endpoints

- `POST /api/v1/query` - Semantic search
- `POST /api/v1/capture` - Quick capture
- `GET /api/v1/tasks` - List tasks
- `GET /api/v1/briefing` - Daily briefing
- `POST /api/v1/index/rebuild` - Rebuild index

## License

MIT
