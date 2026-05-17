import logging
import logging.handlers
import os
import time

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import create_tables
from app.services.scheduler import start_scheduler, stop_scheduler
from app.api import research, watchlist, screener, alerts, macro
from app.api import research_v2, usage
from app.api import gap_scanner
from app.api import dip_scanner
from app.api import mcf_scanner
from app.api import broker

settings = get_settings()

# ── Logging setup ─────────────────────────────────────────────────────────────
_LOG_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_formatter = logging.Formatter(_LOG_FMT)

# stdout (always on)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_formatter)

# rotating file → local_debugging/app.log (daily, keep 7 days)
os.makedirs(settings.log_dir, exist_ok=True)
_file_handler = logging.handlers.TimedRotatingFileHandler(
    filename=os.path.join(settings.log_dir, "app.log"),
    when="midnight",
    backupCount=7,
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_stream_handler, _file_handler])
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Stock Research Pro — env: %s", settings.environment)
    logger.info("LLM provider: %s / %s", settings.model_type, settings.model_name)
    logger.info("Logs writing to: %s/app.log", settings.log_dir)

    await create_tables()
    logger.info("Database tables ready")

    start_scheduler()

    from app.services.telegram_handler import start_polling, stop_polling
    start_polling()

    yield

    stop_polling()
    stop_scheduler()
    logger.info("Stock Research Pro shutdown complete")


app = FastAPI(
    title="Stock Research Pro",
    description=(
        "AI-powered stock research platform — day trade and long-term signals, "
        "watchlist monitoring, screener, geopolitical risk analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Request logging middleware ────────────────────────────────────────────────
_req_logger = logging.getLogger("app.requests")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    # Skip noisy health/root pings at INFO; log them at DEBUG
    level = logging.DEBUG if request.url.path in ("/health", "/") else logging.INFO
    _req_logger.log(level, "%s %s %d %.0fms", request.method, request.url.path, response.status_code, ms)
    return response


# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["http://localhost:5173", "http://localhost:3000"]
        if settings.environment == "development"
        else []
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(research.router)
app.include_router(research_v2.router)
app.include_router(usage.router)
app.include_router(watchlist.router)
app.include_router(screener.router)
app.include_router(alerts.router)
app.include_router(macro.router)
app.include_router(gap_scanner.router)
app.include_router(dip_scanner.router)
app.include_router(mcf_scanner.router)
app.include_router(broker.router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "provider": settings.model_type,
        "model": settings.model_name,
        "environment": settings.environment,
    }


@app.get("/")
async def root():
    return {
        "name": "Stock Research Pro API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
