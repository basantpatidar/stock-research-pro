# Stock Research Pro — Complete Setup Guide

> Everything you need to go from zero to a running app.
> Follow steps in order. Estimated total time: 20–30 minutes.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the project](#2-clone-the-project)
3. [API keys — what you need and where to get them](#3-api-keys)
4. [Configure the .env file](#4-configure-the-env-file)
5. [IDE setup (VS Code / IntelliJ)](#5-ide-setup)
6. [Run with Docker (recommended)](#6-run-with-docker-recommended)
7. [Run locally without Docker](#7-run-locally-without-docker)
8. [Frontend setup](#8-frontend-setup)
9. [Verify everything is working](#9-verify-everything-is-working)
10. [Common errors and fixes](#10-common-errors-and-fixes)
11. [Switching LLM providers](#11-switching-llm-providers)
12. [Optional API keys (enhance features)](#12-optional-api-keys)

---

## 1. Prerequisites

Install these before anything else.

### Python 3.12+
- Download: https://www.python.org/downloads/
- Verify: `python3 --version` → should show `3.12.x` or higher
- On Mac with Homebrew: `brew install python@3.12`
- On Windows: `winget install Python.Python.3.12 --source winget` or download from python.org
- **Important:** Python 3.14 is NOT supported — `pydantic-core` requires Python ≤ 3.13. Use 3.12.

### Node.js 20+
- Download: https://nodejs.org/en/download (choose LTS version)
- Verify: `node --version` → should show `v20.x.x` or higher
- On Mac with Homebrew: `brew install node`

### Docker Desktop (for Docker setup)
- Download: https://www.docker.com/products/docker-desktop/
- Install and start Docker Desktop
- Verify: `docker --version` and `docker compose version`
- Note: Docker Desktop must be **running** before you use `docker compose`

### Git
- Download: https://git-scm.com/downloads
- Verify: `git --version`
- On Mac: comes pre-installed or install via Xcode Command Line Tools

---

## 2. Clone the Project

```bash
# Clone your repository
git clone https://github.com/YOUR_USERNAME/stock-research-pro.git

# Enter the project directory
cd stock-research-pro

# Verify structure — you should see these folders
ls
# backend/  frontend/  docker-compose.yml  Makefile  README.md  CLAUDE.md
```

---

## 3. API Keys

You need **at minimum 2 keys** to run the app with full features.
The app will still start without them but some features will return errors.

---

### 3A. LLM Provider — Pick ONE (required)

You only need ONE of these. Pick based on your preference.

---

#### Option 1: Groq — RECOMMENDED (free, fast)

**Why:** Completely free, extremely fast inference, no credit card needed.

1. Go to: https://console.groq.com
2. Click **Sign Up** (top right)
3. Sign up with GitHub, Google, or email
4. After login, click **API Keys** in the left sidebar
5. Click **Create API Key**
6. Give it a name: `stock-research-pro`
7. Copy the key — it looks like: `gsk_xxxxxxxxxxxxxxxxxxxx`
8. Save it — you cannot see it again after closing the dialog

```bash
# In your .env file:
MODEL_TYPE=groq
MODEL_NAME=llama-3.3-70b-versatile
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

**Free tier limits:** 30 requests/minute, 14,400 requests/day — more than enough for personal use.

---

#### Option 2: Ollama — fully local (free, no internet needed)

**Why:** Runs entirely on your machine. No API key, no rate limits, no cost. Needs a decent computer (8GB+ RAM).

1. Go to: https://ollama.com/download
2. Download and install for your OS (Mac/Windows/Linux)
3. Open a terminal and pull the model:
   ```bash
   ollama pull llama3.2
   ```
4. Wait for download (about 2GB)
5. Verify it works:
   ```bash
   ollama run llama3.2
   # Type anything and press Enter, then Ctrl+D to exit
   ```

```bash
# In your .env file:
MODEL_TYPE=ollama
OLLAMA_MODEL=llama3.2
# No API key needed
```

**Note:** Ollama must be running in the background when you use the app. It starts automatically after install on most systems. If not, run `ollama serve` in a terminal.

---

#### Option 3: Google Gemini (free tier available)

1. Go to: https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click **Create API key**
4. Select **Create API key in new project** or choose an existing project
5. Copy the key — it looks like: `AIzaSyxxxxxxxxxxxxxxxxxx`

```bash
# In your .env file:
MODEL_TYPE=gemini
MODEL_NAME=gemini-2.5-flash
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxx
```

**Free tier limits:** 5 requests/minute for `gemini-2.5-flash`, 1,500 requests/day. Set `LLM_TIER=free` in `.env` to enable automatic throttling.

---

#### Option 4: Anthropic Claude (paid, highest quality)

1. Go to: https://console.anthropic.com
2. Click **Sign Up** or **Log In**
3. Add a credit card (required — no free tier for API)
4. Go to **API Keys** in the left sidebar
5. Click **Create Key**
6. Name it: `stock-research-pro`
7. Copy the key — it looks like: `sk-ant-xxxxxxxxxxxx`

```bash
# In your .env file:
MODEL_TYPE=claude
MODEL_NAME=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

**Pricing:** ~$3 per million input tokens, ~$15 per million output tokens. A typical research session uses 2,000–10,000 tokens.

---

#### Option 5: OpenRouter (free models available)

1. Go to: https://openrouter.ai
2. Click **Sign In** (top right) → sign in with Google or GitHub
3. Click your avatar → **Keys**
4. Click **Create Key**
5. Name it: `stock-research-pro`
6. Copy the key — it looks like: `sk-or-v1-xxxxxxxxxxxx`

```bash
# In your .env file:
MODEL_TYPE=openrouter
MODEL_NAME=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxx
```

**Free models:** Search `:free` suffix on https://openrouter.ai/models

---

#### Option 6: OpenAI (paid)

1. Go to: https://platform.openai.com/api-keys
2. Sign in or create an account
3. Click **Create new secret key**
4. Name it: `stock-research-pro`
5. Copy the key — it looks like: `sk-xxxxxxxxxxxxxxxxxxxx`

```bash
# In your .env file:
MODEL_TYPE=openai
MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

---

#### Option 7: Cerebras (free tier)

1. Go to: https://cloud.cerebras.ai
2. Click **Sign Up**
3. After login, go to **API Keys**
4. Click **Create new API key**
5. Copy the key

```bash
# In your .env file:
MODEL_TYPE=cerebras
MODEL_NAME=llama3.3-70b
CEREBRAS_API_KEY=csk-xxxxxxxxxxxxxxxxxxxx
```

---

### 3B. NewsAPI (required for news features)

**Why needed:** Powers the news impact panel, geopolitical events, and sentiment analysis.

1. Go to: 
2. Click **Get API Key** (top right)
3. Fill in the registration form:
   - Choose **Developer** plan (free)
   - Enter your name and email
   - Enter purpose: "Personal stock research project"
4. Check your email for verification link and click it
5. Log in and go to your **Account** page
6. Copy your API key — it looks like: `abc123def456ghi789jkl012mno345pq`

```bash
# In your .env file:
NEWSAPI_KEY=abc123def456ghi789jkl012mno345pq
```

**Free tier limits:** 100 requests/day, headlines only, no full article text.

---

### 3C. Reddit API (optional — enhances sentiment)

**Why needed:** Powers Reddit sentiment analysis from r/wallstreetbets, r/stocks, r/investing.

1. Go to: https://www.reddit.com/prefs/apps
2. Log in to Reddit (or create an account)
3. Scroll down to **Developed Applications**
4. Click **Create App** (or "Create Another App")
5. Fill in:
   - **Name:** `StockResearchPro`
   - **Type:** Select **script**
   - **Description:** `Personal stock research tool`
   - **About URL:** Leave blank
   - **Redirect URI:** `http://localhost:8080`
6. Click **Create app**
7. You will see your app created with two values:
   - **Client ID** — the string directly under the app name (14 characters)
   - **Client Secret** — labeled "secret"

```bash
# In your .env file:
REDDIT_CLIENT_ID=your_14_char_client_id
REDDIT_CLIENT_SECRET=your_secret_here
REDDIT_USER_AGENT=StockResearchPro/1.0 by YourRedditUsername
```

---

## 4. Configure the .env File

```bash
# From the project root
cp .env.example .env
```

Now open `.env` in your editor and fill in your values.

### Complete .env file (copy this, fill in your values)

```bash
# ─────────────────────────────────────────────────────────────
# LLM PROVIDER — change MODEL_TYPE to switch providers
# Only the selected provider's key is needed
# ─────────────────────────────────────────────────────────────
MODEL_TYPE=groq
MODEL_NAME=llama-3.3-70b-versatile
OLLAMA_MODEL=llama3.2

GROQ_API_KEY=                    # https://console.groq.com
CEREBRAS_API_KEY=                # https://cloud.cerebras.ai
OPENROUTER_API_KEY=              # https://openrouter.ai
GEMINI_API_KEY=                  # https://aistudio.google.com/app/apikey
ANTHROPIC_API_KEY=               # https://console.anthropic.com
OPENAI_API_KEY=                  # https://platform.openai.com/api-keys

# ─────────────────────────────────────────────────────────────
# DATA SOURCES
# ─────────────────────────────────────────────────────────────
NEWSAPI_KEY=                     # https://newsapi.org — free, 100 req/day
REDDIT_CLIENT_ID=                # https://reddit.com/prefs/apps — optional
REDDIT_CLIENT_SECRET=            # same page as above — optional
REDDIT_USER_AGENT=StockResearchPro/1.0

# ─────────────────────────────────────────────────────────────
# APPLICATION
# ─────────────────────────────────────────────────────────────
API_KEY=my-super-secret-dev-key  # Choose anything — this protects your API
ENVIRONMENT=development          # development = relaxed auth, verbose logs

# ─────────────────────────────────────────────────────────────
# DATABASES — Docker fills these automatically
# Change only if running locally without Docker
# ─────────────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/stockresearch
REDIS_URL=redis://localhost:6379

# ─────────────────────────────────────────────────────────────
# BACKGROUND JOBS
# ─────────────────────────────────────────────────────────────
SCREENER_INTERVAL_MINUTES=15     # How often screener auto-runs (minutes)
WATCHLIST_ALERT_INTERVAL_MINUTES=5  # How often watchlist is evaluated (minutes)

# ─────────────────────────────────────────────────────────────
# RATE LIMITING
# ─────────────────────────────────────────────────────────────
# free = apply provider RPM caps (recommended for free-tier API keys)
# paid = no LLM rate limiting (use after upgrading to a paid plan)
LLM_TIER=free
YF_REQUESTS_PER_SECOND=2         # yfinance throttle — lower if you see Yahoo 429 errors
```

### Important notes on the .env file

- **Never commit `.env` to Git.** It is already in `.gitignore`.
- Leave unused API keys as empty strings — the app handles missing keys gracefully.
- `API_KEY` can be anything you choose — it is just a password for your own API. Use something memorable like `my-stock-app-key-2025`.
- In `development` mode, the API key check is relaxed. In production, set `ENVIRONMENT=production`.

---

## 5. IDE Setup

### VS Code (recommended)

#### Install recommended extensions

Open VS Code, press `Ctrl+Shift+X` (or `Cmd+Shift+X` on Mac) and install:

| Extension | Publisher | Why |
|---|---|---|
| Python | Microsoft | Python language support |
| Pylance | Microsoft | Python type checking |
| Ruff | Astral Software | Python linting |
| ESLint | Microsoft | TypeScript/React linting |
| Prettier | Prettier | Code formatting |
| TypeScript Vue Plugin | Vue | Better TS support |
| Docker | Microsoft | Docker Compose support |
| DotENV | mikestead | .env file syntax highlighting |
| REST Client | Huachao Mao | Test API endpoints in .http files |

#### Configure Python interpreter

1. Open the project in VS Code: `code .`
2. Press `Ctrl+Shift+P` → type `Python: Select Interpreter`
3. Select Python 3.12 (you may need to point to your venv — see Section 7)
4. If you don't see 3.12, click `Enter interpreter path` → navigate to your Python 3.12 installation

#### VS Code settings (optional but recommended)

Create `.vscode/settings.json` in the project root:

```json
{
  "python.defaultInterpreterPath": "./backend/.venv/bin/python",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll.ruff": true
  },
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[typescriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "typescript.preferences.importModuleSpecifier": "relative",
  "files.exclude": {
    "**/__pycache__": true,
    "**/.pytest_cache": true,
    "**/node_modules": true
  }
}
```

#### Launch configurations (run with F5)

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Backend (FastAPI)",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/backend",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/backend"
      },
      "envFile": "${workspaceFolder}/.env",
      "console": "integratedTerminal"
    }
  ]
}
```

---

### IntelliJ IDEA / PyCharm

#### Python SDK configuration

1. Open the project: **File → Open** → select the `stock-research-pro` folder
2. Go to **File → Project Structure** (or `Cmd+;` on Mac)
3. Under **Project**, click **SDK → Add SDK → Python SDK**
4. Select **Virtualenv Environment → New**
5. Set location to: `backend/.venv`
6. Set base interpreter to Python 3.12
7. Click **OK**

#### Mark directories as source roots

1. Right-click `backend/` → **Mark Directory as → Sources Root**
2. Right-click `frontend/src` → **Mark Directory as → Sources Root**

#### Environment variables in run configuration

1. Go to **Run → Edit Configurations**
2. Click **+** → **Python**
3. Set:
   - **Script path:** point to uvicorn or set as module `uvicorn`
   - **Parameters:** `app.main:app --reload --port 8000`
   - **Working directory:** `backend/`
   - **Environment variables:** Click the folder icon → **+** and add each variable from `.env`
   - Or check **EnvFile** plugin and point to `.env`

#### Node.js / Frontend in IntelliJ

1. Go to **File → Settings → Languages & Frameworks → Node.js**
2. Set Node interpreter to your Node 20 installation
3. Open `frontend/package.json` → right-click → **Show npm Scripts**
4. Double-click `dev` to run the frontend

---

## 6. Run with Docker (Recommended)

This is the easiest way. One command starts everything.

```bash
# Make sure Docker Desktop is running first

# From the project root
docker compose up --build
```

This starts:
- **Backend** on http://localhost:8000
- **Frontend** on http://localhost:5173
- **PostgreSQL** on localhost:5432
- **Redis** on localhost:6379

First run takes 3–5 minutes to build images. Subsequent starts are fast.

### Useful Docker commands

```bash
# Start in background (detached)
docker compose up --build -d

# View logs
docker compose logs -f

# View only backend logs
docker compose logs -f backend

# Stop everything
docker compose down

# Stop and delete all data (reset database)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

### If you change the .env file

```bash
docker compose down
docker compose up --build
```

Docker reads `.env` at startup. Changes require a restart.

---

## 7. Run Locally Without Docker

Use this if you want faster iteration during development.

### Backend setup

```bash
cd backend

# Create virtual environment
python3.12 -m venv .venv

# Activate it
source .venv/bin/activate          # Mac/Linux
.venv\Scripts\activate             # Windows PowerShell
.venv\Scripts\activate.bat         # Windows Command Prompt

# Install dependencies
pip install -r requirements.txt

# Verify the install
python -c "import fastapi, langgraph, yfinance; print('All good')"
```

### Database setup (local PostgreSQL)

If you don't want to use Docker for the database:

1. Install PostgreSQL: https://www.postgresql.org/download/
2. Start PostgreSQL service
3. Create the database:
   ```bash
   psql -U postgres
   CREATE DATABASE stockresearch;
   \q
   ```
4. Update `.env`:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/stockresearch
   ```

### Redis setup (local)

If you don't want to use Docker for Redis:

- Mac: `brew install redis && brew services start redis`
- Windows: Download from https://github.com/microsoftarchive/redis/releases
- Linux: `sudo apt install redis-server && sudo systemctl start redis`

### Run database migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### Start the backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting Stock Research Pro — env: development
INFO:     LLM provider: groq / llama-3.3-70b-versatile
INFO:     Database tables ready
INFO:     Scheduler started
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 8. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create frontend environment file
cp .env.example .env.local    # if .env.example exists in frontend/
# OR create it manually:
```

Create `frontend/.env.local`:

```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_API_KEY=my-super-secret-dev-key   # must match API_KEY in backend .env
```

```bash
# Start the dev server
npm run dev
```

You should see:
```
  VITE v6.x.x  ready in 300ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.x.x:5173/
```

Open http://localhost:5173 in your browser.

### Frontend environment variables explained

| Variable | Value | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend URL for REST calls |
| `VITE_WS_URL` | `ws://localhost:8000` | Backend URL for WebSocket |
| `VITE_API_KEY` | Same as backend `API_KEY` | Authentication header value |

**Important:** `VITE_API_KEY` must exactly match `API_KEY` in your backend `.env`. If they don't match, the frontend will get 401 errors.

---

## 9. Verify Everything is Working

### Check 1: Backend health

Open in browser or run in terminal:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "provider": "groq",
  "model": "llama-3.3-70b-versatile",
  "environment": "development"
}
```

### Check 2: API docs

Open http://localhost:8000/docs in your browser.
You should see the Swagger UI with all endpoints listed.

### Check 3: Frontend loads

Open http://localhost:5173 in your browser.
You should see the Stock Research Pro dashboard with the search bar.

### Check 4: Search a stock

1. Type `AAPL` in the search bar
2. Press Enter or click Research
3. You should see price data, technicals, analyst data load within 5 seconds
4. Click any "Click to analyze" panel — it should expand and run LLM analysis

### Check 5: WebSocket connection

In the top-right corner of the app, you should see a green dot labeled **Live**.
If it shows gray and "Connecting...", the WebSocket connection failed — check that the backend is running.

### Check 6: Run tests

```bash
cd backend
source .venv/bin/activate
PYTHONPATH=. python -m pytest tests/ -v
```

Expected: `45 passed, 1 skipped`

---

## 10. Common Errors and Fixes

### "Connection refused" when searching a stock

**Cause:** Backend is not running or wrong port.
**Fix:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `VITE_API_URL` in `frontend/.env.local` matches the backend port

---

### "401 Unauthorized" errors in browser console

**Cause:** `VITE_API_KEY` in frontend doesn't match `API_KEY` in backend.
**Fix:**
1. Open `frontend/.env.local` — check the value of `VITE_API_KEY`
2. Open backend `.env` — check the value of `API_KEY`
3. They must be identical strings
4. Restart both servers after fixing

---

### "NEWSAPI_KEY not configured" in news panel

**Cause:** `NEWSAPI_KEY` is empty in `.env`.
**Fix:** Get a free key from https://newsapi.org and add it to `.env`, then restart the backend.

---

### LLM provider error: "Invalid API key" or rate limit

**Cause:** Wrong or expired API key, or hit free tier limit.
**Fix:**
1. Double-check the key is correct and not truncated
2. If rate-limited, ensure `LLM_TIER=free` is set in `.env` — this enables automatic throttling before requests are sent
3. Verify the key is set for the correct `MODEL_TYPE` (e.g., Groq key won't work for `MODEL_TYPE=gemini`)
4. Free tier RPM caps: Gemini 5/min, Groq 30/min, Cerebras 30/min. Switch to `MODEL_TYPE=ollama` for no limits.

---

### Yahoo Finance 429 errors in logs

**Cause:** Multiple tools hitting Yahoo Finance simultaneously during a research session.
**Fix:**
1. Lower `YF_REQUESTS_PER_SECOND` in `.env` (e.g., from `2` to `1`)
2. Restart the backend: `docker compose restart backend`
3. These are warnings — tools return `{"error": "..."}` gracefully and the agent continues

---

### Ollama not responding

**Cause:** Ollama is installed but not running.
**Fix:**
```bash
ollama serve    # start Ollama in a terminal, keep it running
# In another terminal, verify:
curl http://localhost:11434/api/tags
```

---

### "Cannot connect to Docker daemon"

**Cause:** Docker Desktop is not running.
**Fix:** Open Docker Desktop application and wait for it to fully start (the whale icon in your system tray should be still, not animated).

---

### Database migration error on startup

**Cause:** Tables don't exist yet or migration hasn't run.
**Fix:**
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

---

### Port already in use (EADDRINUSE)

**Cause:** Something else is running on port 8000 or 5173.
**Fix:**
```bash
# Find and kill the process using port 8000 (Mac/Linux)
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID_NUMBER> /F
```

---

### Frontend shows blank page after search

**Cause:** Usually a JavaScript error — open browser DevTools (F12) → Console tab to see the error.
**Common causes:**
- Backend returned unexpected data structure
- TypeScript type mismatch (shouldn't happen in production build)
- Network error (check Network tab in DevTools)

---

### "ModuleNotFoundError" when starting backend

**Cause:** Virtual environment not activated or dependencies not installed.
**Fix:**
```bash
cd backend
source .venv/bin/activate    # Mac/Linux
pip install -r requirements.txt
```

---

## 11. Switching LLM Providers

This is the main reason the app was built provider-agnostic. One change, no code edits.

Open `.env` and change just these two lines:

```bash
# Switch to Ollama (local, free)
MODEL_TYPE=ollama
OLLAMA_MODEL=llama3.2

# Switch to Gemini
MODEL_TYPE=gemini
MODEL_NAME=gemini-2.5-flash

# Switch to Claude
MODEL_TYPE=claude
MODEL_NAME=claude-sonnet-4-5

# Switch back to Groq
MODEL_TYPE=groq
MODEL_NAME=llama-3.3-70b-versatile
```

Then restart the backend:

```bash
# If using Docker
docker compose restart backend

# If running locally
# Ctrl+C to stop uvicorn, then:
uvicorn app.main:app --reload --port 8000
```

Verify the switch worked:
```bash
curl http://localhost:8000/health
# "provider" field should show your new MODEL_TYPE
```

---

## 12. Optional API Keys

These enhance specific features but are not required to run the app.

### StockTwits (no key needed)

The StockTwits sentiment feed works without an API key. The public endpoint is used directly. If you hit rate limits, the feature gracefully degrades.

### Google Trends (no key needed)

Uses the `pytrends` library which accesses Google Trends without an API key. No setup required. Install with:
```bash
pip install pytrends
```

### Alpha Vantage (if you want better fundamental data)

- Get free key: https://www.alphavantage.co/support/#api-key
- 25 requests/day free, 500/day with free registration
- Currently not wired in — future enhancement

### Polygon.io (for intraday and higher volume data)

- Website: https://polygon.io/dashboard/signup
- Free tier: end-of-day data only, 5 API calls/minute
- Paid: real-time data, unlimited calls
- Currently not wired in — future enhancement

### FINRA (for dark pool data — V2 feature)

- Website: https://www.finra.org/finra-data/browse-catalog/equity-short-interest
- Free public data, no API key
- Requires scraping their search page — V2 outstanding item

---

## Quick Start Checklist

Use this as a final checklist before your first run:

- [ ] Python 3.12+ installed (`python3 --version`)
- [ ] Node.js 20+ installed (`node --version`)
- [ ] Docker Desktop installed and running (if using Docker)
- [ ] Project cloned (`git clone ...`)
- [ ] `.env` created (`cp .env.example .env`)
- [ ] At least one LLM API key filled in (Groq recommended)
- [ ] `NEWSAPI_KEY` filled in
- [ ] `API_KEY` set to something memorable
- [ ] `frontend/.env.local` created with `VITE_API_KEY` matching backend `API_KEY`
- [ ] App started (`docker compose up --build` or manual start)
- [ ] `/health` endpoint returns `{"status": "ok"}`
- [ ] Frontend loads at http://localhost:5173
- [ ] Searching `AAPL` returns price data

---

## Summary — Minimum Setup in 5 Commands

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/stock-research-pro.git
cd stock-research-pro

# 2. Configure
cp .env.example .env
# Edit .env: add GROQ_API_KEY and NEWSAPI_KEY and set API_KEY

# 3. Configure frontend
echo "VITE_API_URL=http://localhost:8000" > frontend/.env.local
echo "VITE_WS_URL=ws://localhost:8000" >> frontend/.env.local
echo "VITE_API_KEY=my-super-secret-dev-key" >> frontend/.env.local

# 4. Start
docker compose up --build

# 5. Open
open http://localhost:5173   # Mac
# or navigate to http://localhost:5173 in your browser
```

Done. The app is running.
