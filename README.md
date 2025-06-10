# 🧠 Agent Compute Marketplace (AgentCloud)

An AI-powered sandbox where autonomous agents negotiate cloud compute (GPUs, CPUs) and settle transactions using real-world payment rails (Stripe, PayPal, crypto). The project demonstrates agent-to-agent markets, AI-driven negotiation, secure payments, and audit-grade logging—ideal proof-of-work for infra / AI / fintech recruiters.

---

## ⚙️ Key Features

| Feature                                 | Why it matters                                                                            |
| --------------------------------------- | ----------------------------------------------------------------------------------------- |
| 🤝 **Autonomous Buyer & Seller Agents** | Simulate real-time supply–demand negotiation without human input.                         |
| 🧠 **GPT-Powered Negotiation Engine**   | Uses LangChain / AutoGen + GPT-4 to generate dynamic counter-offers and acceptance logic. |
| 💳 **Payment Integrations**             | Stripe (test mode), PayPal sandbox, optional ERC-20—showcases executable commerce flows.  |
| 📈 **Real-Time UI & Replay**            | Streamlit/React dashboard visualizes deal progress and lets recruiters replay sessions.   |
| 🧾 **Audit Logging & Policy Controls**  | Enterprise-grade traceability; every agent action and payment webhook is persisted.       |

---

## 🏗️ Tech Stack

| Layer         | Tools                                               |
| ------------- | --------------------------------------------------- |
| Agent Logic   | Python 3.11, GPT-4 (LangChain / AutoGen)            |
| Backend       | FastAPI                                             |
| Payments      | Stripe SDK, PayPal SDK, Web3.py (ERC-20)            |
| Database      | Development: SQLite                                 |
|               | Production: PostgreSQL + TimescaleDB                |
| Observability | OpenTelemetry, structured JSON logs                 |
| Frontend      | Streamlit _(fast)_ or React + Tailwind _(polished)_ |

---

## 📂 Project Structure

```text
agent-compute-marketplace/
├── agents/            # Buyer & seller agent classes
├── api/               # FastAPI routes and schemas
├── core/              # Shared settings, dependency utilities
├── db/                # SQLAlchemy models and DB session helpers
├── alembic/           # Migration env; versions/ sub-folder holds auto scripts
│   └── alembic.ini
├── negotiation/       # GPT-powered FSM + prompt templates
├── payments/          # Stripe, PayPal, crypto gateway adapters
├── tests/             # Pytest suites
├── docs/              # Extra markdown or ADRs (optional)
├── main.py            # FastAPI entry-point
├── .env.example
├── requirements.txt
├── pyproject.toml
├── setup.md
├── .gitignore
└── README.md
```

## Setup

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

4. Initialize the database:

```bash
alembic upgrade head
```

5. Run the development server:

```bash
uvicorn main:app --reload
```

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `ruff .`
- Create database migration: `alembic revision --autogenerate -m "description"`

## Environment Variables

Required environment variables in `.env`:

- `DATABASE_URL`: Database connection string
- `STRIPE_KEY`: Stripe API key
- `PAYPAL_CLIENT_ID`: PayPal client ID
- `PAYPAL_SECRET`: PayPal secret key
- `OPENAI_API_KEY`: OpenAI API key

**Database Strategy**: SQLite remains valid for quick hacking; set `DATABASE_URL` to switch.

## API Documentation

Once running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Setup and Migrations

### Initial Setup

1. Create a PostgreSQL database:

```bash
createdb agent_compute_marketplace
```

2. Set up your database URL in the environment:

```bash
export DATABASE_URL=postgresql://username:password@localhost/agent_compute_marketplace
```

3. Run all migrations:

```bash
alembic upgrade head
```

### Working with Migrations

When making database schema changes:

1. Create a new migration:

```bash
alembic revision --autogenerate -m "description of changes"
```

2. Review the generated migration in `alembic/versions/`

3. Apply the migration:

```bash
alembic upgrade head
```

4. To rollback a migration:

```bash
alembic downgrade -1
```

### Environment-specific Configuration

- Local development: Use `DATABASE_URL` environment variable
- Staging/Production: Set `DATABASE_URL` in your deployment environment
- Testing: Uses `test_agent_marketplace` database by default

### Troubleshooting

If you encounter issues with enum types in PostgreSQL:

1. Check current enum values: `\dT+ enum_name`
2. Verify table structure: `\d table_name`
3. Make sure all migrations have been applied: `alembic current`
