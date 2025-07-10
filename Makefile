.PHONY: dev test lint docker-build docker-up docker-down help install format check-format

# Default target
help:
	@echo "Agent Compute Marketplace - Development Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  dev              - Start development server with auto-reload"
	@echo "  test             - Run pytest with coverage"
	@echo "  lint             - Run linting with ruff and black"
	@echo "  format           - Format code with black"
	@echo "  check-format     - Check code formatting"
	@echo "  install          - Install dependencies with Poetry"
	@echo "  migrate          - Run database migrations"
	@echo "  docker-build     - Build Docker image"
	@echo "  docker-up        - Start all services with docker-compose"
	@echo "  docker-up-core   - Start core services (db, api, dashboard)"
	@echo "  docker-up-observability - Start observability services (prometheus, grafana, jaeger)"
	@echo "  docker-up-minimal - Start minimal services (db, api only)"
	@echo "  docker-down      - Stop all services"
	@echo "  docker-logs      - View logs from all services"
	@echo "  clean            - Clean up temporary files"
	@echo "  setup            - Complete development setup"

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

# Docker commands
docker-build:
	docker build -t agentcloud:$(shell git rev-parse --short HEAD) .

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean:
	docker-compose down -v --rmi all --remove-orphans

# Service-specific Docker commands
docker-up-core:
	docker-compose up --build db api dashboard

docker-up-observability:
	docker-compose up --build prometheus grafana jaeger

docker-up-minimal:
	docker-compose up --build db api

# Utility commands
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

setup: install migrate
	@echo "Development environment setup complete!"
	@echo "Run 'make dev' to start the development server"

# Production deployment helpers
prod-build:
	docker build -t agentcloud:latest .

prod-up:
	docker-compose -f docker-compose.yml up -d

prod-down:
	docker-compose -f docker-compose.yml down

# Dashboard
dashboard:
	cd dashboard && poetry run streamlit run streamlit_app.py 