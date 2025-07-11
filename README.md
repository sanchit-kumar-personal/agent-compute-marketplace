# 🧠 Agent Compute Marketplace (AgentCloud)

[![CI](https://github.com/yourusername/agent-compute-marketplace/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/agent-compute-marketplace/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)

An AI-powered sandbox where autonomous agents negotiate cloud compute (GPUs, CPUs) and settle transactions using real-world payment rails (Stripe, PayPal, crypto). The project demonstrates agent-to-agent markets, AI-driven negotiation, secure payments, and audit-grade logging—ideal proof-of-work for infra / AI / fintech recruiters.

![dashboard](docs/dashboard.png)

---

## 🚀 Quick Start

### Local Docker Development

1. **Clone and setup:**

```bash
git clone https://github.com/yourusername/agent-compute-marketplace.git
cd agent-compute-marketplace
cp env.example .env
# Edit .env with your API keys
```

2. **Start all services:**

```bash
make docker-up
```

3. **Access the application:**

- **API:** http://localhost:8000
- **Dashboard:** http://localhost:8501
- **Grafana:** http://localhost:3000 (admin/admin)
- **Jaeger:** http://localhost:16686
- **Prometheus:** http://localhost:9090

### Local Development

1. **Install dependencies:**

```bash
make install
```

2. **Setup database:**

```bash
make migrate
```

3. **Start development server:**

```bash
make dev
```

### Available Commands

Run `make help` to see all available commands:

- `make dev` - Start development server
- `make test` - Run tests with coverage
- `make lint` - Run linting and formatting
- `make docker-up` - Start all services
- `make docker-down` - Stop all services

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

## Environment Configuration

The project uses environment variables for configuration. All developers use the same approach:

### Setup Environment Variables

```bash
# Copy the example environment file
cp env.example .env

# Edit .env to add your actual API keys
# The file contains sensible defaults for Docker networking
```

### Key Environment Variables

The environment file includes configuration for:

- **Database**: Uses Docker networking (`db:5432`) when running with Docker Compose
- **Observability**: Configured for Docker service names (`jaeger:4317`, `prometheus:9090`)
- **External APIs**: Add your own API keys for OpenAI, Stripe, PayPal
- **Application Settings**: Debug mode, service names, etc.

### Docker vs Local Development

The `env.example` file is pre-configured for Docker development. When you run `docker-compose up`, the services automatically connect using Docker's internal networking.

For local development (running services directly on your host), you would need to update the URLs to use `localhost` instead of service names.

## 🐳 Docker Commands

## Environment Variables

Create a `.env` file from the `env.example` template:

```bash
cp env.example .env
```

Required environment variables:

- `DATABASE_URL`: Database connection string
- `STRIPE_API_KEY`: Stripe API key (use test keys for development)
- `STRIPE_WEBHOOK_SECRET`: Stripe webhook secret
- `PAYPAL_CLIENT_ID`: PayPal client ID from sandbox
- `PAYPAL_SECRET`: PayPal secret key from sandbox
- `OPENAI_API_KEY`: OpenAI API key

**Database Strategy**: The application supports both SQLite (development) and PostgreSQL (production).

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

The application uses OpenTelemetry with Jaeger for distributed tracing. All services are included in the main docker-compose.yml.

1. Start all services (including Jaeger):

```bash
make docker-up
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

All monitoring services are included in the main docker-compose.yml:

```bash
make docker-up  # Starts all services including Prometheus + Grafana
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
