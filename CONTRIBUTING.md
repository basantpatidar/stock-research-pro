# Contributing to Stock Research Pro

## Getting started

### Prerequisites
- Python 3.12+
- Node 20+
- Docker + Docker Compose (optional but recommended)
- A free [Groq API key](https://console.groq.com) or local [Ollama](https://ollama.ai)
- A free [NewsAPI key](https://newsapi.org)

### Local setup

```bash
git clone https://github.com/yourusername/stock-research-pro
cd stock-research-pro
cp .env.example .env   # fill in your keys
make install           # installs Python + Node dependencies
make up                # starts all services via Docker
```

Or without Docker:
```bash
make backend    # terminal 1 — FastAPI on :8000
make frontend   # terminal 2 — Vite on :5173
```

---

## Project structure

```
stock-research-pro/
├── backend/app/
│   ├── agent/          # LangGraph ReAct graph + state + prompts
│   ├── tools/          # 20 data tools — one file each
│   ├── api/            # FastAPI route handlers
│   ├── services/       # Background scheduler + alert engine
│   ├── db/             # SQLAlchemy models + Alembic migrations
│   └── llm/            # Provider-agnostic LLM factory
└── frontend/src/
    ├── pages/          # ResearchPage, WatchlistPage, ScreenerPage, MacroPage
    ├── components/     # UI components grouped by page
    ├── hooks/          # useSSE, useWebSocket, useWatchlist, useScreener
    └── services/       # Axios API client
```

---

## Adding a new data tool

1. Create `backend/app/tools/my_tool.py`:

```python
from langchain_core.tools import tool

@tool
def my_new_tool(ticker: str) -> dict:
    """
    One-line description — this becomes the tool's docstring the LLM reads.
    Be specific: say what the tool returns and when to call it.
    """
    try:
        # your logic here
        return {"ticker": ticker, "data": ...}
    except Exception as e:
        return {"error": f"Failed: {str(e)}"}   # never raise — always return error dict
```

2. Register it in `backend/app/agent/graph.py`:

```python
from app.tools.my_tool import my_new_tool

ALL_TOOLS = [
    ...
    my_new_tool,   # add here
]
```

3. Write a test in `tests/tools/test_tools.py` — see existing tests for patterns.

That's it. The agent discovers and uses it automatically.

---

## Running tests

```bash
make test           # full suite
make test-tools     # tool unit tests only
make test-api       # API integration tests only
make test-cov       # with coverage report
```

All tests run against SQLite — no Postgres needed for testing.

---

## Code style

```bash
make lint       # ruff — catches unused imports, undefined names
make fmt        # black — auto-formats to 100 char line length
make typecheck  # tsc --noEmit — TypeScript frontend
```

CI enforces all three on every PR. Fix lint before pushing.

---

## Switching LLM providers

Change one line in `.env`:

```bash
MODEL_TYPE=groq        # fastest free option
MODEL_TYPE=ollama      # fully local, no API key
MODEL_TYPE=gemini      # best free-tier quality
MODEL_TYPE=claude      # highest quality, paid
```

No code changes needed anywhere.

---

## Database migrations

After changing `backend/app/db/models.py`:

```bash
make migration MSG="add_portfolio_table"   # generates migration file
make migrate                                # applies it
```

---

## Pull request checklist

- [ ] Tests pass (`make test`)
- [ ] Lint clean (`make lint`)
- [ ] New tools have at least 3 unit tests
- [ ] New API endpoints have at least 2 integration tests
- [ ] Tools always return `{"error": "..."}` on failure — never raise
- [ ] `.env.example` updated if new env vars added
