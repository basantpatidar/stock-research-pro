.PHONY: help up down logs backend frontend test lint fmt migrate shell clean

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "Stock Research Pro — dev commands"
	@echo ""
	@echo "  make up          Start all services (Docker)"
	@echo "  make down        Stop all services"
	@echo "  make logs        Tail all service logs"
	@echo "  make backend     Start backend only (local, no Docker)"
	@echo "  make frontend    Start frontend only (local, no Docker)"
	@echo "  make test        Run all backend tests"
	@echo "  make test-watch  Run tests in watch mode"
	@echo "  make lint        Lint backend with ruff"
	@echo "  make fmt         Format backend with black"
	@echo "  make migrate     Run pending Alembic migrations"
	@echo "  make migration   Generate new migration (MSG='description')"
	@echo "  make shell       Open Python shell with app context"
	@echo "  make clean       Remove cache + test artifacts"
	@echo ""

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker compose up --build

up-detach:
	docker compose up --build -d

down:
	docker compose down

down-volumes:
	docker compose down -v

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

tail-log:
	tail -f local_debugging/app.log

# ── Local dev (no Docker) ─────────────────────────────────────────────────────
backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

# ── Testing ───────────────────────────────────────────────────────────────────
test:
	cd backend && PYTHONPATH=. python -m pytest tests/ -v --tb=short

test-tools:
	cd backend && PYTHONPATH=. python -m pytest tests/tools/ -v --tb=short

test-api:
	cd backend && PYTHONPATH=. python -m pytest tests/api/ -v --tb=short

test-watch:
	cd backend && PYTHONPATH=. python -m pytest tests/ -v --tb=short -f

test-cov:
	cd backend && PYTHONPATH=. python -m pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# ── Lint & format ─────────────────────────────────────────────────────────────
lint:
	cd backend && ruff check app/ --select E,F,I --ignore E501

fmt:
	cd backend && black app/ tests/ --line-length 100

fmt-check:
	cd backend && black --check app/ --line-length 100

typecheck:
	cd frontend && npx tsc --noEmit

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	cd backend && alembic upgrade head

migrate-down:
	cd backend && alembic downgrade -1

migration:
	cd backend && alembic revision --autogenerate -m "$(MSG)"

db-reset:
	cd backend && alembic downgrade base && alembic upgrade head

# ── Utilities ─────────────────────────────────────────────────────────────────
shell:
	cd backend && PYTHONPATH=. python -c "\
from app.config import get_settings; \
from app.llm.factory import get_llm; \
settings = get_settings(); \
print(f'Provider: {settings.model_type} / {settings.model_name}'); \
import code; code.interact(local=locals())"

health:
	curl -s http://localhost:8000/health | python3 -m json.tool

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.db" -not -path "*/migrations/*" -delete 2>/dev/null || true
	rm -rf backend/.pytest_cache backend/htmlcov backend/coverage.xml
	rm -rf frontend/dist frontend/.vite
	@echo "Clean complete"
