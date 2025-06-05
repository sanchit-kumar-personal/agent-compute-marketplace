# Setup Instructions

## Prerequisites

- Python 3.11 or higher
- pip (included with Python)
- For production & development: PostgreSQL 14+

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/agent-compute-marketplace.git
cd agent-compute-marketplace
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp env.example .env
# Edit .env with your configuration
```

Required environment variables:

- DATABASE_URL (see Database Configuration section below)
- STRIPE_KEY, PAYPAL_CLIENT_ID, PAYPAL_SECRET (payment providers)
- OPENAI_API_KEY

## Database Configuration

### PostgreSQL (Recommended for Development)

1. **Install PostgreSQL**:

   - macOS: `brew install postgresql`
   - Ubuntu: `sudo apt install postgresql postgresql-contrib`
   - Windows: Download from postgresql.org

2. **Start PostgreSQL service**:

   ```bash
   # macOS with Homebrew
   brew services start postgresql

   # Ubuntu/Debian
   sudo systemctl start postgresql
   ```

3. **Configure your `.env` file**:

   ```bash
   DATABASE_URL=postgresql://postgres:password@localhost:5432/agent_marketplace
   ```

### SQLite (Fallback/Testing Only)

For testing or when PostgreSQL is not available:

```bash
# In your .env file
DATABASE_URL=sqlite:///./app.db
```

**Note**: SQLite is now primarily used for unit tests. PostgreSQL is recommended for all development work.

## Database Migrations

### Initial Setup (PostgreSQL)

```bash
# Generate initial migration for PostgreSQL
alembic revision --autogenerate -m "Initial PostgreSQL migration"

# Apply migrations
alembic upgrade head
```

### Development Workflow

```bash
# After making model changes
alembic revision --autogenerate -m "Description of changes"

# Apply new migrations
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

## Development Server

1. **Start the application**:

   ```bash
   python main.py
   ```

2. **Verify setup**:
   - API: http://localhost:8000
   - Health check: http://localhost:8000/healthz
   - API docs: http://localhost:8000/docs

The health endpoint will show whether you're using PostgreSQL or SQLite.

## Testing

### Unit Tests (SQLite)

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run only unit tests
pytest -m unit
```

### Integration Tests (PostgreSQL)

```bash
# Setup test database
createdb test_agent_marketplace

# Run integration tests
pytest -m integration

# Run specific test file
pytest tests/test_specific.py
```

## Development Tools

- **Format code**: `black .`
- **Lint code**: `ruff check .`
- **Type checking**: `mypy .` (if installed)

## Troubleshooting

### PostgreSQL Connection Issues

1. **Check PostgreSQL is running**:

   ```bash
   # macOS
   brew services list | grep postgresql

   # Linux
   sudo systemctl status postgresql
   ```

2. **Test connection manually**:

   ```bash
   psql -h localhost -U postgres -d postgres
   ```

3. **Check logs**:

   ```bash
   # macOS Homebrew
   tail -f /opt/homebrew/var/log/postgres.log

   # Linux
   sudo journalctl -u postgresql
   ```

### Migration Issues

1. **Reset migrations** (development only):

   ```bash
   # Drop all tables
   alembic downgrade base

   # Recreate from scratch
   alembic upgrade head
   ```

2. **Manual migration**:

   ```bash
   # Connect to PostgreSQL
   psql -h localhost -U postgres -d agent_marketplace

   # Run SQL commands manually
   ```

## Production Deployment

For production deployment with PostgreSQL:

1. Set `ENVIRONMENT=production` in your environment
2. Use a managed PostgreSQL service (AWS RDS, Google Cloud SQL, etc.)
3. Update `DATABASE_URL` with production credentials
4. Run migrations: `alembic upgrade head`

## Architecture Notes

- **Database**: PostgreSQL for development, production compatibility
- **ORM**: SQLAlchemy with SQLModel for type safety
- **Migrations**: Alembic for schema versioning
- **Connection Pooling**: Configured for PostgreSQL performance
- **Async Support**: Available for PostgreSQL operations
- **Testing**: SQLite for unit tests, PostgreSQL for integration tests
