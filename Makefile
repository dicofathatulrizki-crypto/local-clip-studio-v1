.PHONY: dev dev-backend dev-frontend install install-dev install-ai test lint typecheck clean setup docker-build docker-up help

# ─── Development ───────────────────────────────────────────────

dev: dev-backend  ## Start backend development server

dev-backend:  ## Start FastAPI with hot reload
	@echo "Starting backend server on http://localhost:8765"
	@cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8765

dev-backend-no-reload:  ## Start FastAPI without hot reload
	@echo "Starting backend server on http://localhost:8765"
	@cd backend && uvicorn main:app --host 0.0.0.0 --port 8765

# ─── Installation ──────────────────────────────────────────────

install:  ## Install base dependencies
	pip install -e "."

install-dev: install  ## Install dev dependencies
	pip install -e ".[dev]"

install-ai: install  ## Install AI dependencies
	pip install -e ".[ai]"

install-all: install-dev install-ai  ## Install all dependencies

setup:  ## Full project setup
	@echo "Setting up Local Clip Studio..."
	@pip install -e ".[dev]"
	@scripts/setup.sh
	@echo "Setup complete. Run 'make dev' to start."

# ─── Testing ───────────────────────────────────────────────────

test:  ## Run all tests
	pytest -x -v

test-unit:  ## Run unit tests only
	pytest -x -v tests/unit/ -m "not slow and not gpu"

test-integration:  ## Run integration tests only
	pytest -x -v tests/integration/ -m "not slow and not gpu"

test-slow:  ## Run all tests including slow tests
	pytest -v

test-cov:  ## Run tests with coverage report
	pytest --cov=backend --cov-report=term --cov-report=html

test-benchmarks:  ## Run performance benchmarks
	pytest tests/performance/ --benchmark-only

# ─── Linting & Type Checking ───────────────────────────────────

lint:  ## Run ruff linter
	ruff check backend/ tests/

format:  ## Format code with ruff
	ruff format backend/ tests/

typecheck:  ## Run mypy type checking
	mypy backend/

check: lint typecheck test-unit  ## Run all checks (lint + types + tests)

# ─── Database ──────────────────────────────────────────────────

db-init:  ## Initialize database (create tables)
	python -c "from backend.infrastructure.database.engine import init_db; init_db()"

db-migrate:  ## Auto-generate new migration
	alembic -c backend/infrastructure/database/migrations/alembic.ini revision --autogenerate -m "$(message)"

db-upgrade:  ## Apply pending migrations
	alembic -c backend/infrastructure/database/migrations/alembic.ini upgrade head

db-downgrade:  ## Rollback last migration
	alembic -c backend/infrastructure/database/migrations/alembic.ini downgrade -1

# ─── Docker ────────────────────────────────────────────────────

docker-build:  ## Build Docker images
	docker compose -f docker/docker-compose.yml build

docker-up:  ## Start services with Docker
	docker compose -f docker/docker-compose.yml up -d

docker-down:  ## Stop Docker services
	docker compose -f docker/docker-compose.yml down

docker-logs:  ## View Docker logs
	docker compose -f docker/docker-compose.yml logs -f

# ─── Maintenance ───────────────────────────────────────────────

clean:  ## Clean build artifacts
	@rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "Cleaned build artifacts"

clean-all: clean  ## Deep clean including venv
	@rm -rf venv/ .venv/
	@echo "Deep clean complete"

# ─── Help ──────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
