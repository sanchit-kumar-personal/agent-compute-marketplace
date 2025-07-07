# 🧠 Agent Compute Marketplace (AgentCloud)

An AI-powered sandbox where autonomous agents negotiate cloud compute (GPUs, CPUs) and settle transactions using real-world payment rails (Stripe, PayPal, crypto). The project demonstrates agent-to-agent markets, AI-driven negotiation, secure payments, and audit-grade logging—ideal proof-of-work for infra / AI / fintech recruiters.

![dashboard](docs/dashboard.png)

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

6. Start the Streamlit dashboard:

```bash
cd dashboard
streamlit run streamlit_app.py
```

The dashboard will be available at http://localhost:8501

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `ruff .`
- Create database migration: `alembic revision --autogenerate -m "description"`

## Environment Variables

Required environment variables in `.env`:

- `DATABASE_URL`: Database connection string
- `STRIPE_KEY`: Stripe API key
- `PAYPAL_BASE`: PayPal API base URL (defaults to sandbox URL)
- `PAYPAL_CLIENT_ID`: PayPal client ID from sandbox developer dashboard
- `PAYPAL_SECRET`: PayPal secret key from sandbox developer dashboard
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

## Dashboard Features

The Streamlit dashboard provides real-time monitoring of agent negotiations:

- **Auto-refresh**: Toggle 5-second auto-refresh in the sidebar
- **Quote History**: Adjust the number of visible quotes using the rows slider
- **Negotiation Replay**: Click any quote row and use "Replay negotiation" to watch the turn-by-turn negotiation process
- **Price Trends**: View historical price trends for all quotes

## Tracing

The application uses OpenTelemetry with Jaeger for distributed tracing. To use tracing:

1. Start the Jaeger container:

```bash
docker compose -f docker-compose.tracing.yml up -d
```

2. Run the application normally. All FastAPI endpoints will be automatically traced.

3. View traces in the Jaeger UI:

- Open http://localhost:16686
- Select "agentcloud" from the Service dropdown
- Click "Find Traces" to view request traces

The traces will show:

- HTTP request paths and methods
- Request/response timing
- Dependencies and relationships between services

## Logging

The application uses structured JSON logging with OpenTelemetry trace context injection. All log output is in JSON format and includes:

- ISO timestamps
- Log levels
- OpenTelemetry trace IDs (when available)
- Custom contextual fields

To view logs in pretty-printed JSON format:

```bash
uvicorn main:app --reload | jq
```

Example log output:

```json
{
  "timestamp": "2024-01-20T10:30:45.123Z",
  "level": "info",
  "event": "stripe.capture_succeeded",
  "quote_id": "qt_abc123",
  "amount_usd": 99.99,
  "provider_id": "pi_xyz789",
  "trace_id": "0af7651916cd43dd8448eb211c80319c"
}
```

## Metrics

The application exposes Prometheus metrics at `/metrics` endpoint for monitoring quote throughput and other operational metrics.

### Available Metrics

**Custom Business Metrics:**

- `agentcloud_quotes_total` - Total number of quotes created
- `agentcloud_negotiation_latency_seconds` - Time taken for negotiation rounds (histogram)
- `agentcloud_payment_success_total` - Total successful payments by provider (counter with labels)

**Standard FastAPI Metrics:**

- HTTP request rates, response times, status codes
- Request duration histograms
- Active connections

### Security

In production, the metrics endpoint can be protected using:

```bash
# Set environment variables for production
export ENVIRONMENT=production
export METRICS_AUTH_TOKEN=your-secure-token-here

# Access metrics with authentication
curl -H "X-Metrics-Auth: your-secure-token-here" http://localhost:8000/metrics
```

The endpoint also allows access from private networks (10.x.x.x, 192.168.x.x, 172.x.x.x) for VPN access.

### Running Prometheus + Grafana

```bash
docker compose -f docker-compose.metrics.yml up -d  # Prometheus + Grafana
uvicorn main:app --reload  # run the app
# Open localhost:9090 -> verify agentcloud_quotes_total
# Grafana default creds admin/admin -> import dashboard ID 11159 (FastAPI metrics)
```

### Grafana Dashboard Setup

1. Open http://localhost:3000 (admin/admin)
2. Add Prometheus data source: `http://prometheus:9090`
3. Import dashboard ID 11159 for FastAPI metrics
4. Create custom panels for business metrics like `agentcloud_quotes_total`

## Audit Log

The system maintains comprehensive audit logs of all quote and payment actions in the `audit_logs` table. Every API request to `/api` endpoints that results in a successful response (2xx status codes) is automatically logged.

### Audit Actions Tracked

- `quote_created` - When a new quote request is submitted
- `negotiation_turn` - During quote negotiation processes
- `quote_accepted` - When a quote is accepted
- `quote_rejected` - When a quote is rejected
- `payment_succeeded` - When a payment is successfully processed
- `payment_failed` - When a payment fails

### PostgreSQL Query Example

```sql
-- Get all audit logs for a specific quote
SELECT action, payload FROM audit_logs WHERE quote_id=42;
```

### Database Schema

The `audit_logs` table contains:

- `id` (Primary Key)
- `quote_id` (Foreign Key to quotes table, indexed)
- `action` (Enum of audit actions, indexed)
- `payload` (JSON blob with action details)
- `created_at` (Timestamp, defaults to current time)

All quote and payment events are automatically captured through middleware and direct logging in payment services.
