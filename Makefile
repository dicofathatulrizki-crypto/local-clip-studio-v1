# Local Clip Studio

.PHONY: dev install test lint typecheck clean docker-build docker-up

# Development
dev:
	@echo "Starting development servers..."
	@cd frontend && bun dev &
	@python -m backend.main

install:
	@echo "Installing backend dependencies..."
	@pip install -e ".[dev]"
	@echo "Installing frontend dependencies..."
	@cd frontend && bun install

install-ai:
	@echo "Installing AI dependencies..."
	@pip install -e ".[ai]"

# Testing
test:
	@echo "Running tests..."
	@pytest tests/ -x -v $(ARGS)

test-unit:
	@pytest tests/unit/ -x -v $(ARGS)

test-integration:
	@pytest tests/integration/ -x -v $(ARGS)

test-coverage:
	@pytest tests/ -x -v --cov=backend --cov-report=term-missing --cov-report=html

# Code quality
lint:
	@ruff check backend/

format:
	@ruff format backend/

typecheck:
	@mypy backend/

check-all: lint typecheck test

# Cleanup
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ htmlcov/ .coverage

clean-all: clean
	@rm -rf ~/.localclip/

# Docker
docker-build:
	@docker compose -f docker/docker-compose.yml build

docker-up:
	@docker compose -f docker/docker-compose.yml up -d

docker-down:
	@docker compose -f docker/docker-compose.yml down

# Alembic migrations
migrate:
	@alembic upgrade head

migrate-create:
	@alembic revision --autogenerate -m "$(message)"

migrate-rollback:
	@alembic downgrade -1

# Setup
setup:
	@bash scripts/setup.sh

download-models:
	@bash scripts/download_models.sh
