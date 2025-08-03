#!/bin/bash
# Startup script for the API container
# Runs database initialization and then starts the FastAPI server

set -e

echo "🚀 Starting Agent Compute Marketplace API..."

# Initialize database (migrations + seeding)
echo "📋 Step 1: Database initialization"
python scripts/init_db.py

# Start the FastAPI server
echo "🌐 Step 2: Starting FastAPI server"
exec uvicorn main:app --host 0.0.0.0 --port 8000 