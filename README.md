# Aqua

<div align="center">

[![CI](https://github.com/DankChamp/aqua/actions/workflows/ci.yml/badge.svg)](https://github.com/DankChamp/aqua/actions/workflows/ci.yml)
[![CodeQL](https://github.com/DankChamp/aqua/actions/workflows/codeql.yml/badge.svg)](https://github.com/DankChamp/aqua/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-00FF9C.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Void Linux](https://img.shields.io/badge/Void_Linux-runit%20%2B%20XBPS-1c1c1c?logo=linux&logoColor=white)](https://voidlinux.org)

</div>

**Personal AI research & study assistant. Quizzes, knowledge capture, literature review, web search. Locally hosted, privacy-first.**

---

## How Aqua Differs from Emma & Luna

| Aspect | **Emma** | **Luna** | **Aqua** |
|--------|----------|----------|----------|
| **Primary Role** | Personal OS / life management | Coding agent / software engineering | Research / study / knowledge |
| **Core Features** | Planning, tasks, reminders, voice, scheduling | Code gen, tool calling, file ops, LSP | Quizzes, web search, PDF ingestion, citations |
| **Target User** | Daily productivity, R&D coordination | Developers, engineers | Students, researchers, lifelong learners |
| **Memory** | 4-tier (long-term, project, daily, convo) | Session-based, context-aware | Knowledge base, vector search (ChromaDB) |
| **Interface** | CLI + PySide6 GUI + Voice | TUI (Rich) + CLI | CLI + Web UI (planned) |

**Aqua is purpose-built for academic and research workflows** — not general coding or life management.

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/DankChamp/aqua
cd aqua

# Core dependencies
pip install -e .

# Full features (ChromaDB, embeddings, PDF parsing)
pip install -e ".[all]"

# Configure
cp .env.example .env
# Edit .env with your LLM provider settings

# Run
./start.sh          # API server on http://localhost:8000
aqua "explain quantum entanglement"  # CLI query
```

### Requirements
- Python 3.10+
- Ollama (or any OpenAI-compatible endpoint)
- Optional: ChromaDB for vector search, sentence-transformers for embeddings

---

## Core Capabilities

### 🔬 Research Assistant
- **Web search** via DuckDuckGo (no API key needed)
- **Literature review** — ingest papers, extract key findings
- **Citation management** — auto-generate references in multiple formats
- **Summarization** — condense long documents to key points

### 📚 Study Tools
- **Quiz generation** — create practice questions from any topic
- **Spaced repetition** — intelligent review scheduling
- **Flashcards** — auto-generate from notes or documents
- **Progress tracking** — learning analytics dashboard

### 📄 Document Processing
- **PDF ingestion** — extract text, tables, figures
- **Vector search** — semantic retrieval via ChromaDB
- **Knowledge base** — build personal research library

### 🔒 Privacy-First
- Runs entirely locally (Ollama + local embeddings)
- No data leaves your machine unless you configure cloud LLMs
- SQLite for structured data, ChromaDB for vectors

---

## Configuration

All settings via `.env` (Pydantic Settings):

```bash
# LLM Provider
AQUA_LLM_PROVIDER=ollama          # ollama | openai | anthropic
AQUA_OLLAMA_BASE_URL=http://localhost:11434
AQUA_OLLAMA_MODEL=llama3.1:8b

# OpenAI-compatible
AQUA_OPENAI_BASE_URL=http://localhost:1234/v1
AQUA_OPENAI_API_KEY=
AQUA_OPENAI_MODEL=your-model

# Anthropic
AQUA_ANTHROPIC_API_KEY=sk-ant-...

# Vector Search (optional)
AQUA_CHROMA_PATH=./data/chroma
AQUA_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Search
AQUA_DUCKDUCKGO_MAX_RESULTS=10
```

---

## Usage

### CLI
```bash
# Direct query
aqua "summarize the key papers on transformer architecture"

# With document context
aqua --pdf ./papers/attention.pdf "explain the attention mechanism"

# Generate quiz
aqua --quiz "cellular respiration" --questions 10

# Interactive mode
aqua --interactive
```

### API Server
```bash
./start.sh
# POST http://localhost:8000/query
# POST http://localhost:8000/quiz
# POST http://localhost:8000/ingest
```

### Web UI (planned)
```bash
# Coming soon: React-based dashboard for study sessions
```

---

## Architecture

```
aqua/
├── main.py                 # FastAPI app entry
├── config.py               # Pydantic Settings
├── start.sh                # Launch script
├── aqua_voice.py           # Voice interface (Vosk + Piper)
├── api/
│   ├── routes/             # /query, /quiz, /ingest, /search
│   └── deps.py             # Dependency injection
├── core/
│   ├── research/           # Web search, summarization, citations
│   ├── study/              # Quiz gen, spaced repetition, flashcards
│   ├── knowledge/          # ChromaDB vector store, document ingestion
│   └── llm/                # Provider abstractions
├── cli/
│   └── aqua.py             # CLI entry (Typer/Rich)
├── automation/             # Scheduled tasks, review reminders
├── bridge/                 # External integrations
├── voice/                  # Vosk STT + Piper TTS
├── web/                    # Static assets for web UI
└── data/                   # SQLite, ChromaDB, uploads
```

---

## Development

```bash
# Install with dev extras
pip install -e ".[all]"
pip install ruff mypy pytest pytest-asyncio httpx

# Lint
ruff check .

# Type check
mypy .

# Test
pytest -q --tb=short

# Run API
python main.py
```

---

## Roadmap

- [ ] Web UI dashboard (React + Vite)
- [ ] Anki export for flashcards
- [ ] Zotero/Mendeley integration
- [ ] Multi-modal (image analysis for diagrams)
- [ ] Collaborative study rooms
- [ ] Offline-first PWA
- [ ] Plugin system for custom quiz types

---

## Contributing

PRs welcome! Please:

1. Fork the repo & create a feature branch
2. Run `ruff check . && mypy . && pytest -q` locally
3. Follow the existing code style
4. Add tests for new functionality
5. Open a PR with a clear description

---

## License

MIT License — see [LICENSE](LICENSE) for details.