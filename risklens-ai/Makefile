# ============================================
# RiskLens AI — Makefile
# ============================================

.PHONY: help setup up down restart logs seed test lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Docker ---
up: ## Start all services
	docker-compose -f docker/docker-compose.yml up --build -d

down: ## Stop all services
	docker-compose -f docker/docker-compose.yml down

restart: ## Restart all services
	docker-compose -f docker/docker-compose.yml down && docker-compose -f docker/docker-compose.yml up --build -d

logs: ## Tail all logs
	docker-compose -f docker/docker-compose.yml logs -f

logs-api: ## Tail backend logs
	docker-compose -f docker/docker-compose.yml logs -f risklens-api

logs-ui: ## Tail frontend logs
	docker-compose -f docker/docker-compose.yml logs -f risklens-ui

# --- Development ---
setup: ## Initial project setup
	cp .env.example .env
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

dev-api: ## Run backend in dev mode
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-ui: ## Run frontend in dev mode
	cd frontend && npm run dev

# --- Database ---
seed: ## Seed database with sample data
	cd backend && python -m scripts.seed_database

# --- Testing ---
test: ## Run all tests
	cd backend && pytest tests/ -v

test-cov: ## Run tests with coverage
	cd backend && pytest tests/ -v --cov=app --cov-report=html

# --- Code Quality ---
lint: ## Lint backend code
	cd backend && ruff check app/
	cd backend && mypy app/

format: ## Format backend code
	cd backend && ruff format app/

# --- Cleanup ---
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name node_modules -exec rm -rf {} +
	rm -rf frontend/dist
