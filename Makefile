.PHONY: dev test lint format check-format install migrate cleanup-reservations reset-demo docker-up docker-down docker-logs clean dashboard help

# Default target
help:
	@echo "Agent Compute Marketplace - Development Commands"
	@echo ""
	@echo "🐳 Docker Commands (Recommended):"
	@echo "  docker-up        - Start all services (auto-migrates & seeds)"
	@echo "  docker-down      - Stop all services"
	@echo "  docker-logs      - View logs from all services"
	@echo "  reset-demo       - Reset demo environment"
	@echo "  cleanup-reservations - Clean up expired reservations"
	@echo ""
	@echo "💻 Local Development Commands:"
	@echo "  dev              - Start development server with auto-reload"
	@echo "  test             - Run pytest with coverage"
	@echo "  lint             - Run linting with ruff and black"
	@echo "  format           - Format code with black"
	@echo "  migrate          - Run database migrations (if not using Docker)"
	@echo ""
	@echo "🔧 Utility Commands:"
	@echo "  install          - Install dependencies with Poetry"
	@echo "  clean            - Clean up temporary files"

# Development
dev:
	poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Testing
test:
	poetry run pytest -v --cov=. --cov-report=term-missing

# Linting and formatting
lint:
	poetry run ruff check .
	poetry run black --check .

format:
	poetry run black .
	poetry run ruff check . --fix

check-format:
	poetry run black --check .

# Dependencies
install:
	poetry install

# Database
migrate:
	poetry run alembic upgrade head

migrate-create:
	poetry run alembic revision --autogenerate -m "$(MSG)"

# v1.0 Database utilities
reset-demo:
	./scripts/reset_demo.sh

cleanup-reservations:
	python3 scripts/cleanup_reservations.py

# Docker commands (simplified)
docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Utility commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Dashboard (for local development)
dashboard:
	cd dashboard && poetry run streamlit run streamlit_app.py 