# Stock Research Pro

AI-powered stock research platform for day trading and long-term investment decisions.

## Features

- **Stock research dashboard** — price history, technicals (RSI/MACD/Bollinger), news impact, analyst consensus, earnings history, insider activity
- **Signal convergence score** — 0–100 score aggregating all signals into one number
- **Geopolitical & macro engine** — VIX, sector heatmap, active world events with cascade impact analysis
- **Watchlist with live signals** — background evaluation every 5 minutes, WebSocket push alerts
- **Stock screener** — filter by market cap, volume, price drop, sector. Auto-monitor in background.
- **Provider-agnostic LLM** — swap between Groq, Ollama, Gemini, Claude, OpenAI, Cerebras via one env var

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · LangGraph · APScheduler |
| AI | LangGraph ReAct agent · 20 tools · Any LLM provider |
| Frontend | React 18 · TypeScript · Vite · Recharts · Zustand |
| Database | PostgreSQL · SQLAlchemy async · Alembic |
| Cache | Redis |
| Real-time | SSE (agent reasoning stream) · WebSocket (live alerts) |
| Data sources | yfinance · NewsAPI · Reddit PRAW · StockTwits · SEC EDGAR · GDELT |
| Infrastructure | Docker · Docker Compose · GitHub Actions |

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/yourusername/stock-research-pro
cd stock-research-pro
cp .env.example .env
```

Edit `.env` — at minimum set:

```bash
MODEL_TYPE=groq                          # or ollama (free, no key needed)
GROQ_API_KEY=your_groq_key_here          # free at console.groq.com
NEWSAPI_KEY=your_newsapi_key_here        # free at newsapi.org
API_KEY=your-secret-key                  # anything you choose
```

### 2. Run with Docker

```bash
docker-compose up --build
```

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### 3. Run locally (without Docker)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## LLM Provider Setup

Change `MODEL_TYPE` in `.env` — no code changes needed anywhere:

| Provider | MODEL_TYPE | Model name | Cost |
|---|---|---|---|
| Ollama (local) | `ollama` | `llama3.2` | Free |
| Groq | `groq` | `llama-3.3-70b-versatile` | Free tier |
| Cerebras | `cerebras` | `llama3.3-70b` | Free tier |
| OpenRouter | `openrouter` | `meta-llama/llama-3.3-70b-instruct:free` | Free |
| Gemini | `gemini` | `gemini-2.5-flash` | Free tier |
| Claude | `claude` | `claude-sonnet-4-5` | Paid |
| OpenAI | `openai` | `gpt-4o-mini` | Paid |

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/research/` | POST | Run full agent research on a ticker |
| `/research/stream` | GET | Stream agent reasoning via SSE |
| `/watchlist/` | GET/POST | Get or add watchlist items |
| `/watchlist/{ticker}` | DELETE | Remove from watchlist |
| `/watchlist/signals` | GET | Get active buy/sell signals |
| `/screener/run` | POST | Run screener with filters |
| `/screener/presets` | GET/POST | Manage saved presets |
| `/alerts/ws` | WS | WebSocket live alert stream |
| `/alerts/history` | GET | Get alert history |
| `/macro/all` | GET | Macro environment + sectors + geo events |
| `/health` | GET | Health check with provider info |

## Environment Variables

See `.env.example` for all variables with descriptions.

## Project Structure

```
stock-research-pro/
├── backend/
│   └── app/
│       ├── agent/          # LangGraph ReAct agent
│       ├── tools/          # 20 data tools (one file each)
│       ├── api/            # FastAPI routes
│       ├── services/       # Background jobs + alert engine
│       ├── db/             # PostgreSQL models + migrations
│       └── llm/            # Provider-agnostic LLM factory
└── frontend/
    └── src/
        ├── pages/          # Research, Watchlist, Screener, Macro
        ├── components/     # Reusable UI components
        ├── hooks/          # useSSE, useWebSocket, useWatchlist, useScreener
        └── services/       # API client
```

## Adding a New Tool

1. Create `backend/app/tools/my_tool.py` with a `@tool` decorated function
2. Import it in `backend/app/agent/graph.py` and add to `ALL_TOOLS`
3. That's it — the agent automatically discovers and uses it

## License

MIT
