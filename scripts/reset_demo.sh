#!/bin/bash
# Demo Reset Script - Clean database and reseed for fresh demo

set -e

echo "🔄 Resetting demo environment..."

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if we're in Docker or local environment
if command -v docker-compose &> /dev/null && docker-compose ps | grep -q "db"; then
    echo "📦 Using Docker environment"
    
    # Clean tables via Docker
    docker-compose exec -T db psql -U agentcloud -d agentcloud << EOF
TRUNCATE TABLE audit_logs, transactions, reservations, quotes, compute_resources RESTART IDENTITY CASCADE;
EOF
    
    # Restart API to trigger automatic reseeding
    echo "🔄 Restarting API to trigger automatic reseeding..."
    docker-compose restart api
    
else
    echo "💻 Using local environment"
    
    # Check if database is accessible
    if ! python3 -c "from core.dependencies import get_settings; get_settings()" &> /dev/null; then
        echo "❌ Cannot connect to database. Make sure it's running and .env is configured."
        exit 1
    fi
    
    # Clean tables locally
    python3 -c "
from sqlalchemy import create_engine, text
from core.dependencies import get_settings
settings = get_settings()
engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    conn.execute(text('TRUNCATE TABLE audit_logs, transactions, reservations, quotes, compute_resources RESTART IDENTITY CASCADE'))
    conn.commit()
print('📊 Tables cleaned')
"
    
    # Reseed resources using the automatic initialization
    echo "🌱 Reseeding compute resources..."
    python3 scripts/init_db.py
fi

echo "✅ Demo environment reset complete!"
echo ""
echo "📋 Ready for demo:"
echo "   - All quotes, transactions, and audit logs cleared"
echo "   - Fresh compute resource inventory loaded"
echo "   - Available: 100 GPU, 500 CPU, 50 TPU units"
echo ""
echo "🚀 Start demo with:"
echo "   curl http://localhost:8000/api/v1/resources/availability" 