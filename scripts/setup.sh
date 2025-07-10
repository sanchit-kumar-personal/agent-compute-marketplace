#!/bin/bash
set -e

echo "🚀 Setting up Agent Compute Marketplace development environment..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "📦 Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "🐳 Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Docker Compose is not installed. Please install Docker Compose first."
    echo "Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

# Create .env file from template
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp env.example .env
    echo "⚠️  Please edit .env with your API keys and configuration"
else
    echo "✅ .env file already exists"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
poetry install

# Initialize Poetry lock file if it doesn't exist
if [ ! -f "poetry.lock" ]; then
    echo "🔒 Creating poetry.lock file..."
    poetry lock
fi

# Check if PostgreSQL is running (optional)
if command -v pg_isready &> /dev/null; then
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo "✅ PostgreSQL is running"
        echo "🗄️  Running database migrations..."
        poetry run alembic upgrade head
    else
        echo "⚠️  PostgreSQL is not running. Database migrations skipped."
        echo "   You can run 'make docker-up' to start all services with Docker."
    fi
else
    echo "⚠️  PostgreSQL not found. Database migrations skipped."
    echo "   You can run 'make docker-up' to start all services with Docker."
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env with your API keys"
echo "2. Run 'make docker-up' to start all services with Docker"
echo "3. Or run 'make dev' for local development"
echo "4. Visit http://localhost:8000 for the API"
echo "5. Visit http://localhost:8501 for the dashboard"
echo ""
echo "Available commands:"
echo "  make help           - Show all available commands"
echo "  make dev            - Start development server"
echo "  make test           - Run tests"
echo "  make docker-up      - Start all services with Docker"
echo "  make docker-down    - Stop all services"
echo "" 