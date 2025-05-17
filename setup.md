# Setup Instructions

## Prerequisites

- Python 3.11 or higher
- pip (included with Python)
- For production: PostgreSQL 14+ with TimescaleDB extension

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/agent-compute-marketplace.git
cd agent-compute-marketplace
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your configuration
```

Required environment variables:

- DATABASE_URL (see Database Configuration section below)
- STRIPE_KEY
- PAYPAL_CLIENT_ID
- PAYPAL_SECRET
- OPENAI_API_KEY

## Database Configuration

### Development (SQLite)

For local development, use SQLite by setting in your `.env`:

```
DATABASE_URL=sqlite:///./app.db
```

### Production (PostgreSQL + TimescaleDB)

1. Install PostgreSQL and TimescaleDB
2. Create a database and enable the TimescaleDB extension
3. Set the DATABASE_URL in your `.env`:

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

4. Initialize the database:

```bash
# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Apply migrations
alembic upgrade head
```

5. Start the development server:

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `ruff .`
- Create new migration: `alembic revision --autogenerate -m "Description"`
- Apply migrations: `alembic upgrade head`
