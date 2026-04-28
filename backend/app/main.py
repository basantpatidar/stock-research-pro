from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.db.database import create_tables
from app.services.scheduler import start_scheduler, stop_scheduler
from app.api import research, watchlist, screener, alerts, macro
from app.api import research_v2, usage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────
    logger.info(f"Starting Stock Research Pro — env: {settings.environment}")
    logger.info(f"LLM provider: {settings.model_type} / {settings.model_name}")

    await create_tables()
    logger.info("Database tables ready")

    start_scheduler()

    yield

    # ── Shutdown ─────────────────────────────────────────────
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

# CORS — allow React dev server in development
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

# ── Mount all routers ─────────────────────────────────────────────────────────
app.include_router(research.router)
app.include_router(research_v2.router)
app.include_router(usage.router)
app.include_router(watchlist.router)
app.include_router(screener.router)
app.include_router(alerts.router)
app.include_router(macro.router)


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
